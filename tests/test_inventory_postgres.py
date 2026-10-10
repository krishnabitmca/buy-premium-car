"""Real PostgreSQL boundaries, using a disposable database on a local test server.

Set CARSCANNER_TEST_DATABASE_URL to a localhost admin database connection.
The fixture creates and removes its own random database; it never resets an
existing application database. No marketplace request is made by these tests.
"""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import urllib.request
from uuid import uuid4

import pytest

psycopg=pytest.importorskip('psycopg')
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from api import search
from src.inventory_db import search_inventory
from src.inventory_db import iter_inventory
from src.inventory_ingestion import ingest_vehicles
from src.inventory_refresh_planner import schedule_refreshes
from src.inventory_refresh_worker import claim_jobs, process_job, recover_jobs, complete_job, run_batch
from src.models import Vehicle
from src.source_adapters import AdapterResult

pytestmark=pytest.mark.integration


@pytest.fixture(scope='module')
def disposable_database():
    admin_url=os.getenv('CARSCANNER_TEST_DATABASE_URL')
    if not admin_url:
        pytest.skip('CARSCANNER_TEST_DATABASE_URL is not configured')
    params=conninfo_to_dict(admin_url)
    # Guard against accidentally pointing integration tests at hosted production.
    if params.get('host') not in {'127.0.0.1','localhost','::1'} or params.get('hostaddr'):
        pytest.fail('Integration tests require a localhost-only PostgreSQL server')
    name='carscanner_test_'+uuid4().hex
    with psycopg.connect(admin_url,autocommit=True) as admin:
        for role in ('anon','authenticated','service_role'):
            if not admin.execute('select 1 from pg_roles where rolname=%s',(role,)).fetchone():
                admin.execute(sql.SQL('create role {} nologin').format(sql.Identifier(role)))
        admin.execute(sql.SQL('create database {}').format(sql.Identifier(name)))
    url=make_conninfo(admin_url,dbname=name)
    try:
        with psycopg.connect(url) as conn:
            for migration in sorted(Path('supabase/migrations').glob('*.sql')):
                conn.execute(migration.read_text(encoding='utf-8'))
        yield url
    finally:
        with psycopg.connect(admin_url,autocommit=True) as admin:
            admin.execute(sql.SQL('drop database {} with (force)').format(sql.Identifier(name)))


@pytest.fixture
def db(disposable_database,monkeypatch):
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL',disposable_database)
    monkeypatch.setenv('CARSCANNER_INVENTORY_FIRST','true')
    monkeypatch.setenv('CARSCANNER_ALLOW_LIVE_COVERAGE_FALLBACK','false')
    monkeypatch.setenv('CARSCANNER_INVENTORY_EXPIRE_MINUTES','10080')
    with psycopg.connect(disposable_database,row_factory=dict_row) as conn:
        conn.execute('truncate public.sources,public.vehicles,public.search_demand restart identity cascade')
        yield conn


def add_source(db,name='Fixture Dealer'):
    row=db.execute("""insert into public.sources(source_key,name,url,source_type,adapter_status)
                      values (%s,%s,'https://fixture.invalid/catalog','dealer','live') returning source_id""",
                   (name.lower().replace(' ','_'),name)).fetchone()
    source_id=row['source_id']
    db.execute("""insert into public.source_capabilities(source_id,capability_type,capability_value)
                  values (%s,'brand','BMW')""",(source_id,))
    db.execute("""insert into public.source_adapters(source_id,adapter_key,status)
                  values (%s,%s,'verified')""",(source_id,name+'_fixture'))
    db.commit()
    return source_id


def vehicle(**kwargs):
    data=dict(source_name='Fixture Dealer',source_tier=1,url='https://fixture.invalid/car/1',
              title='BMW X1',brand='BMW',model='X1',year_manufacture=2024,
              mileage_km=10000,price_lakh=30,condition_signal='used',
              live_verified=True,vin='WBA12345678901234',seller_city='Delhi',seller_state='Delhi')
    data.update(kwargs)
    return Vehicle(**data)


def ingest(db,**kwargs):
    add_source(db)
    v=vehicle(**kwargs)
    assert ingest_vehicles([v])['observations']==1
    return v


@pytest.mark.parametrize('initial,current,filters',[(30,45,{'budget_max':40}),(45,30,{'budget_min':40})])
def test_budget_cannot_select_an_older_qualifying_price(db,initial,current,filters):
    v=ingest(db,price_lakh=initial)
    ingest_vehicles([replace(v,price_lakh=current)])
    rows,sources,count=search_inventory(query='BMW X1',condition='used',return_count=True,**filters)
    assert rows==[] and sources==[] and count==0
    rows,_=search_inventory(query='BMW X1',condition='used')
    assert len(rows)==1 and rows[0]['price_lakh']==current


@pytest.mark.parametrize('live_verified,sold_signal',[(False,False),(False,True),(True,True)])
def test_latest_negative_observation_cannot_resurrect_available_history(db,live_verified,sold_signal):
    ingest(db)
    db.execute("""insert into public.vehicle_observations
                  (vehicle_id,listing_id,source_id,observed_at,price_lakh,live_verified,sold_signal)
                  select vehicle_id,listing_id,source_id,now(),30,%s,%s from public.listings""",
               (live_verified,sold_signal))
    db.commit()
    assert search_inventory(query='BMW X1',return_count=True)==([],[],0)


def test_observation_id_breaks_equal_timestamp_ties(db):
    v=ingest(db)
    ingest_vehicles([replace(v,price_lakh=45)])
    db.execute("update public.vehicle_observations set observed_at='2026-10-10T00:00:00Z'")
    db.commit()
    rows,_=search_inventory()
    assert rows[0]['price_lakh']==45


def test_expired_offer_does_not_appear_in_results_or_count(db):
    ingest(db)
    db.execute("update public.listings set last_verified_at=now()-interval '8 days'")
    db.commit()
    assert search_inventory(return_count=True)==([],[],0)


def test_explicit_sold_page_without_price_retires_existing_offer(db):
    v=ingest(db)
    sold=replace(v,sold_signal=True,live_verified=False,price_lakh=None,brand=None,model=None)
    counts=ingest_vehicles([sold])
    assert counts=={'vehicles':0,'listings':1,'observations':1}
    assert db.execute('select status from public.listings').fetchone()['status']=='sold'
    assert db.execute('select count(*) as n from public.vehicle_observations where sold_signal').fetchone()['n']==1
    assert search_inventory()==([],[])


def test_fetch_failure_and_unknown_sold_url_do_not_remove_stock(db):
    v=ingest(db)
    assert ingest_vehicles([replace(v,live_verified=False)])['observations']==0
    assert ingest_vehicles([replace(v,url='https://fixture.invalid/unknown',sold_signal=True)])['observations']==0
    assert len(search_inventory()[0])==1


def test_sold_offer_keeps_other_sources_offer_available(db):
    v=ingest(db)
    add_source(db,'Second Dealer')
    second=replace(v,source_name='Second Dealer',url='https://fixture.invalid/second',price_lakh=32)
    ingest_vehicles([second])
    ingest_vehicles([replace(v,sold_signal=True,live_verified=False)])
    rows,_=search_inventory()
    assert len(rows)==1 and rows[0]['price_lakh']==32
    assert rows[0]['source_count']==1 and rows[0]['offers'][0]['source']=='Second Dealer'


@contextmanager
def api_server():
    server=ThreadingHTTPServer(('127.0.0.1',0),search.handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_address[1]}/api/search'
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def post_search(monkeypatch,body,source_names):
    # Provider traffic is an external boundary; the DB and HTTP handler are real.
    monkeypatch.setattr(search,'plan_sources',lambda **kw:[{'name':n,'adapter_status':'live'} for n in source_names])
    def unexpected_crawl(*args,**kwargs):
        raise AssertionError('This inventory request must not crawl marketplaces')
    monkeypatch.setattr(search,'live_inventory',unexpected_crawl)
    # Run demand writes synchronously to avoid background work racing DB cleanup.
    monkeypatch.setattr(search._DEMAND_EXECUTOR,'submit',lambda fn,**kw:fn(**kw))
    with api_server() as url:
        request=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=10) as response:
            assert response.status==200
            return json.load(response)


@pytest.mark.parametrize('condition',['used','demo'])
def test_real_database_rows_reach_http_client_with_multiple_offers(db,monkeypatch,condition):
    v=ingest(db,condition_signal=condition)
    add_source(db,'Second Dealer')
    ingest_vehicles([replace(v,source_name='Second Dealer',url='https://fixture.invalid/second',price_lakh=32)])
    # Newer verification of the expensive offer must not relabel the cheapest.
    old=datetime.now(timezone.utc)-timedelta(hours=2)
    db.execute('update public.vehicle_observations set observed_at=%s where price_lakh=30',(old,))
    db.execute('update public.listings set last_verified_at=%s where source_id=(select source_id from public.sources where name=%s)',(old,'Fixture Dealer'))
    db.commit()
    payload=post_search(monkeypatch,{'query':'BMW X1','condition':condition,'budget_max':40,'destination':'Bengaluru'},['Fixture Dealer','Second Dealer'])
    assert payload['ok'] and payload['mode']=='inventory'
    assert payload['total_results']==1
    row=payload['results'][0]
    assert isinstance(row['vehicle_id'],str) and isinstance(row['price_lakh'],float)
    assert row['condition_signal']==condition and row['source_count']==2
    assert row['purchase_context']['mode']=='interstate'
    assert datetime.fromisoformat(row['observed_at'])==old
    assert datetime.fromisoformat(row['last_verified_at'])==old
    assert {offer['price_lakh'] for offer in row['offers']}=={30,32}
    assert all(offer['observed_at'] and offer['last_verified_at'] for offer in row['offers'])


def test_scheduler_claim_worker_ingestion_and_http_boundary(db,monkeypatch):
    add_source(db)
    assert schedule_refreshes()==1
    queued=db.execute('select status,metadata from public.inventory_refresh_queue').fetchone()
    assert queued['status']=='queued' and queued['metadata']['freshness']=='expired'
    jobs=claim_jobs(1)
    assert len(jobs)==1 and jobs[0]['status']=='running'
    # Fetch is the only external acquisition boundary replaced by a fixture.
    listing={'source':'Fixture Dealer','brand':'BMW','model':'X1','mfg_year':2024,
             'km':10000,'price_lakh':30,'condition_signal':'used','live_verified':True,
             'url':'https://fixture.invalid/car/1','vin':'WBA12345678901234'}
    monkeypatch.setattr('src.inventory_refresh_worker.BuiltinMarketplaceAdapter.fetch',
                        lambda self,request:AdapterResult(self.source_name,[listing],status='live'))
    assert process_job(jobs[0])['observations']==1
    db.commit()  # Finish fixture read transaction before checking worker writes.
    assert db.execute('select status from public.inventory_refresh_queue').fetchone()['status']=='completed'
    db.commit()
    payload=post_search(monkeypatch,{'query':'BMW X1','condition':'used'},['Fixture Dealer'])
    assert len(payload['results'])==1 and payload['mode']=='inventory'


def test_successful_empty_scan_is_fresh_and_other_model_still_scheduled(db,monkeypatch):
    add_source(db)
    assert schedule_refreshes()==1
    job=claim_jobs(1)[0]
    monkeypatch.setattr('src.inventory_refresh_worker.BuiltinMarketplaceAdapter.fetch',
                        lambda self,request:AdapterResult(self.source_name,[],status='live'))
    assert process_job(job)['observations']==0
    assert schedule_refreshes()==0
    monkeypatch.setattr('src.inventory_refresh_planner.load_search_demand',
        lambda **kwargs:[{'brand':'BMW','model':'X1','condition':'used','search_count':1}])
    assert schedule_refreshes()==1
    db.commit()
    assert db.execute("select model from public.inventory_refresh_queue where status='queued'").fetchone()['model']=='X1'


def test_abandoned_claim_recovered_and_old_attempt_cannot_complete(db):
    add_source(db)
    schedule_refreshes()
    first=claim_jobs(1)[0]
    db.execute("update public.inventory_refresh_queue set started_at=now()-interval '31 minutes'")
    db.commit()
    assert recover_jobs()==1
    second=claim_jobs(1)[0]
    assert second['attempt_count']==2
    complete_job(first['refresh_id'],success=True,attempt_count=first['attempt_count'])
    assert db.execute('select status from public.inventory_refresh_queue').fetchone()['status']=='running'
    db.commit()
    complete_job(second['refresh_id'],success=True,attempt_count=second['attempt_count'])
    assert db.execute('select status from public.inventory_refresh_queue').fetchone()['status']=='completed'


def test_retry_backoff_and_exhausted_job_remains_failed(db):
    add_source(db)
    schedule_refreshes()
    for attempt in (1,2,3):
        job=claim_jobs(1)[0]
        assert job['attempt_count']==attempt
        complete_job(job['refresh_id'],success=False,error='blocked',attempt_count=attempt)
        assert recover_jobs()==0
        db.execute("update public.inventory_refresh_queue set completed_at=now()-interval '1 day'")
        db.commit()
        assert recover_jobs()==(1 if attempt<3 else 0)
    schedule_refreshes()
    assert claim_jobs(1)==[]


def test_worker_passes_parser_configuration_and_continues_after_failure(db,monkeypatch):
    add_source(db)
    second=add_source(db,'Other Dealer')
    db.execute("update public.sources set metadata=%s where source_id=%s",
               (json.dumps({'parser_strategy':'custom_fixture'}),second))
    db.commit()
    schedule_refreshes()
    seen=[]
    def fetch(adapter,request):
        seen.append(adapter.source)
        if adapter.source_name=='Fixture Dealer':
            raise RuntimeError('source unavailable')
        return AdapterResult(adapter.source_name,[],status='live')
    monkeypatch.setattr('src.inventory_refresh_worker.BuiltinMarketplaceAdapter.fetch',fetch)
    assert run_batch(10)=={'completed':1,'failed':1}
    assert len(seen)==2
    assert next(s for s in seen if s['name']=='Other Dealer')['metadata']['parser_strategy']=='custom_fixture'


def seed_adapter_inventory(db,monkeypatch):
    from src.inventory_service import run_cycle
    add_source(db)
    rows=[{'source':'Fixture Dealer','brand':'BMW','model':'X1','mfg_year':2024,
           'km':10000+i*1000,'owners':1,'price_lakh':price,'condition_signal':'used',
           'live_verified':True,'url':'https://fixture.invalid/shared-inventory',
           'source_listing_id':f'stock-{i}','vin':f'WBA123456789{i:05d}',
           'price_basis':'asking'} for i,price in enumerate((30,40,50),1)]
    monkeypatch.setattr('src.inventory_refresh_worker.BuiltinMarketplaceAdapter.fetch',
                        lambda self,request:AdapterResult(self.source_name,rows,status='live'))
    assert run_cycle(10)=={'scheduled':1,'completed':1,'failed':0}
    return rows


def test_daily_pipeline_keeps_shared_url_cars_and_paginates_full_price_cohort(db,monkeypatch):
    seed_adapter_inventory(db,monkeypatch)
    monkeypatch.setenv('CARSCANNER_INVENTORY_FIRST','false')
    pages=list(iter_inventory(query='BMW X1',condition='used',page_size=1))
    assert len(pages)==3
    results=[p[0] for p in pages]
    assert {v['price_lakh'] for v in results}=={30,40,50}
    assert len({v['listing_id'] for v in results})==3
    assert all(v['comparable_count']==3 and v['comp_median']==40 for v in results)
    assert all(v['source_tier']==2 and v['price_basis']=='asking' for v in results)
    db.commit()
    db.execute("update public.sources set enabled=false")
    db.commit()
    assert list(iter_inventory(query='BMW X1'))==[]


def test_inventory_comparison_does_not_mix_year_or_price_basis(db,monkeypatch):
    seed_adapter_inventory(db,monkeypatch)
    ingest_vehicles([vehicle(source_listing_id='stock-other-year',vin='WBA12345678999998',
                             year_manufacture=2023,price_lakh=5,price_basis='asking'),
                     vehicle(source_listing_id='stock-on-road',vin='WBA12345678999997',
                             year_manufacture=2024,price_lakh=10,price_basis='on_road')])
    results=[v for p in iter_inventory(query='BMW X1') for v in p]
    asking=[v for v in results if v['mfg_year']==2024 and v['price_basis']=='asking']
    assert len(asking)==3 and all(v['comp_median']==40 for v in asking)
    assert all(v['comp_median'] is None for v in results if v not in asking)


def test_stable_marketplace_id_adopts_existing_url_offer_without_old_price(db):
    original=ingest(db,price_lakh=30)
    before=search_inventory(query='BMW X1')[0][0]['listing_id']
    ingest_vehicles([replace(original,source_listing_id='new-stable-id',price_lakh=40)])
    rows,_=search_inventory(query='BMW X1')
    assert len(rows)==1 and rows[0]['listing_id']==before and rows[0]['price_lakh']==40
    assert rows[0]['source_count']==1
    db.commit()
    assert db.execute('select count(*) as n from public.listings').fetchone()['n']==1
    assert db.execute('select count(*) as n from public.vehicle_observations').fetchone()['n']==2


def test_watch_comparison_needs_known_year_and_consistent_observations(db,monkeypatch):
    seed_adapter_inventory(db,monkeypatch)
    db.execute('update public.vehicles set manufacture_year=null')
    db.commit()
    assert all(v['comp_median'] is None for p in iter_inventory(query='BMW X1') for v in p)
    db.execute('update public.vehicles set manufacture_year=2024')
    db.execute('update public.vehicle_observations set data_consistent=false where price_lakh=50')
    db.commit()
    rows=[v for p in iter_inventory(query='BMW X1') for v in p]
    assert len(rows)==3 and all(v['comparable_count']==2 and v['comp_median'] is None for v in rows)


def test_database_crawl_to_watch_outbox_price_change_and_sold_suppression(db,monkeypatch,tmp_path):
    from scripts import process_alerts as alerts
    from src.inventory_contract import json_inventory_value
    from unittest.mock import Mock
    from urllib.parse import parse_qs
    rows=seed_adapter_inventory(db,monkeypatch)
    user=db.execute("insert into public.deal_watch_users(email) values ('fixture@example.invalid') returning user_id").fetchone()
    criteria={'make':'BMW','model':'X1','condition':'both','budget_min_lakh':25,'budget_max_lakh':35,
              'mileage_max_km':50000,'max_owners':2}
    watch=db.execute("""insert into public.deal_watches(user_id,name,constraints,alert_quality,target_discount_pct)
                      values (%s,'BMW Watch',%s,'good',20) returning *""",
                     (user['user_id'],json.dumps(criteria))).fetchone()
    db.execute("""insert into public.watch_channel_preferences(watch_id,channel,enabled,consent_at)
                  values (%s,'email',true,now())""",(watch['watch_id'],))
    db.commit()
    def request(method,path,payload=None,prefer=None):
        table,_,query=path.partition('?')
        filters=parse_qs(query)
        if table=='deal_watches':
            record=dict(db.execute('select * from public.deal_watches').fetchone())
            record['deal_watch_users']=dict(db.execute('select * from public.deal_watch_users').fetchone())
            record['watch_channel_preferences']=[dict(r) for r in db.execute('select * from public.watch_channel_preferences').fetchall()]
            db.commit()
            return [json_inventory_value(record)]
        assert table=='alert_events'
        if method=='GET':
            values=[filters[k][0].removeprefix('eq.') for k in ('watch_id','listing_id','channel','event_type')]
            result=[dict(r) for r in db.execute('select alert_id,status from public.alert_events where watch_id=%s and listing_id=%s and channel=%s and event_type=%s',values).fetchall()]
        elif method=='POST':
            result=[dict(db.execute('''insert into public.alert_events(user_id,watch_id,listing_id,channel,event_type,status,payload)
                    values (%s,%s,%s,%s,%s,%s,%s) returning alert_id''',
                    tuple(payload[k] for k in ('user_id','watch_id','listing_id','channel','event_type','status'))+
                    (json.dumps(payload['payload']),)).fetchone())]
        else:
            assert method=='PATCH'
            db.execute('update public.alert_events set status=%s,provider_message_id=%s where alert_id=%s',
                       (payload['status'],payload.get('provider_message_id'),filters['alert_id'][0].removeprefix('eq.')))
            result=[]
        db.commit()
        return json_inventory_value(result)
    monkeypatch.setattr(alerts,'sb_request',request)
    provider=Mock(return_value={'id':'fixture-provider-id'})
    monkeypatch.setattr(alerts,'send_resend',provider)
    # A poisoned snapshot in the working directory must never affect matches.
    (tmp_path/'data').mkdir()
    (tmp_path/'data'/'latest.json').write_text('{"vehicles":[{"price_lakh":1}]}')
    monkeypatch.chdir(tmp_path)
    assert alerts.process_alerts()['sent']==1
    assert 'Open original listing' in provider.call_args.args[2]
    assert alerts.process_alerts()['sent']==0
    v=vehicle(url=rows[0]['url'],vin=rows[0]['vin'],source_listing_id='stock-1',
              owner_count=1,price_lakh=29,price_basis='asking')
    ingest_vehicles([v])
    assert alerts.process_alerts()['sent']==1
    ingest_vehicles([replace(v,sold_signal=True,live_verified=False)])
    assert alerts.process_alerts()['matched']==0
    assert provider.call_count==2
    assert db.execute("select count(*) as n from public.alert_events where status='sent'").fetchone()['n']==2
