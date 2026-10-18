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
from src.inventory_refresh_planner import schedule_refreshes, baseline_brand_demands
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
        from src.source_registry_db import close_connection_pool
        close_connection_pool()
        with psycopg.connect(admin_url,autocommit=True) as admin:
            admin.execute(sql.SQL('drop database {} with (force)').format(sql.Identifier(name)))


@pytest.fixture
def db(disposable_database,monkeypatch):
    # Test setup changes source metadata between calls inside the cache TTL.
    monkeypatch.setattr('src.source_intelligence._metadata_cache',None)
    # These fixtures exercise one job at a time; baseline fan-out has its own test.
    monkeypatch.setattr('src.inventory_refresh_planner.baseline_brand_demands',lambda:[])
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL',disposable_database)
    monkeypatch.setenv('CARSCANNER_INVENTORY_FIRST','true')
    monkeypatch.setenv('CARSCANNER_ALLOW_LIVE_COVERAGE_FALLBACK','false')
    monkeypatch.setenv('CARSCANNER_INVENTORY_EXPIRE_MINUTES','10080')
    monkeypatch.setenv('CARSCANNER_CRAWL_DELAY_SECONDS','0')
    with psycopg.connect(disposable_database,row_factory=dict_row) as conn:
        conn.execute('truncate public.sources,public.vehicles,public.search_demand restart identity cascade')
        conn.execute('truncate public.inventory_crawl_leases,public.inventory_pipeline_runs')
        conn.commit()  # External worker connections must not wait on fixture TRUNCATE locks.
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


def test_pooled_connections_roll_back_errors_and_replace_closed_connections(db):
    from src.source_registry_db import _connect
    source=add_source(db)
    before=db.execute('select priority from public.sources where source_id=%s',(source,)).fetchone()['priority']
    db.commit()
    with pytest.raises(ValueError):
        with _connect() as conn:
            conn.execute('update public.sources set priority=999 where source_id=%s',(source,))
            raise ValueError('rollback this transaction')
    assert db.execute('select priority from public.sources where source_id=%s',(source,)).fetchone()['priority']==before
    with _connect() as conn:
        conn.close()
    with _connect() as conn:
        assert conn.execute('select 1 as n').fetchone()['n']==1


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


def test_partial_and_conflicting_identifiers_remain_separate_source_offers(db):
    from src.canonical_identity import candidate_identity
    add_source(db)
    add_source(db,'Other Dealer')
    first=vehicle(vin='PARTIAL1234',url='https://fixture.invalid/partial/1')
    second=replace(first,source_name='Other Dealer',url='https://fixture.invalid/partial/2')
    assert ingest_vehicles([first,second])['observations']==2
    rows=db.execute("select identity_state,identity_confidence from vehicles").fetchall()
    assert len(rows)==2
    assert all(row['identity_state']=='provisional' and row['identity_confidence']==0 for row in rows)
    assert db.execute('select max(identity_confidence) as n from vehicle_observations').fetchone()['n']==0
    # Renewing one source preserves its offer identity rather than multiplying it.
    ingest_vehicles([replace(first,price_lakh=29)])
    assert db.execute('select count(*) as n from listings').fetchone()['n']==2
    assert search_inventory(return_count=True)[2]==2
    conflict=vehicle(url='https://fixture.invalid/conflict/1',
                     chassis_number='WBA12345678901235')
    assert candidate_identity(conflict)[2]['mode']=='conflict'
    ingest_vehicles([conflict])
    assert db.execute("select count(*) as n from vehicles where identity_state='confirmed'").fetchone()['n']==0


def test_identity_audit_reports_legacy_groups_without_rewriting_history(db):
    from src.identity_audit import audit_identities
    ingest(db)
    assert audit_identities()['review_required']==0
    db.execute("update vehicles set identity_key='vin:partial1234',identity_evidence=%s::jsonb",
               (json.dumps({'mode':'vin'}),));db.commit()
    report=audit_identities()
    assert report['read_only'] and not report['truncated']
    assert report['invalid_full_vin']==1 and report['review_required']==1
    assert 'partial1234' not in json.dumps(report)
    assert db.execute('select identity_key from vehicles').fetchone()['identity_key']=='vin:partial1234'
    assert db.execute('select count(*) as n from vehicle_observations').fetchone()['n']==1


def test_manual_source_benchmark_uses_canonical_eligibility_and_read_only_snapshot(db):
    from src.coverage_benchmark import benchmark_database
    v=ingest(db)
    sample={'version':1,'sampling':{'method':'manual_source_review','reviewer':'fixture-reviewer',
            'scope':'Synthetic fixture, not actual market coverage',
            'collected_at':datetime.now(timezone.utc).isoformat()},
            'records':[{'source':'Fixture Dealer','url':v.url,'brand':'BMW','model':'X1',
                        'seller_state':'Delhi','condition':'used','eligible':True}]}
    report=benchmark_database(sample)
    assert report['sample_recall']==1 and report['snapshot_eligible_offers']==1
    assert not report['national_coverage_established']
    ingest_vehicles([replace(v,sold_signal=True,live_verified=False)])
    report=benchmark_database(sample)
    assert report['matched']==0 and report['gaps'][0]['status']=='missing'
    sample['records'][0]['eligible']=False
    report=benchmark_database(sample)
    assert report['eligible_sample']==0 and report['sample_recall'] is None
    assert report['ineligible_indexed_count']==0
    assert db.execute('select count(*) as n from vehicle_observations').fetchone()['n']==2


def test_saved_vehicle_revalidation_keeps_cohorts_and_excludes_latest_sold_offer(db):
    v=ingest(db)
    ingest_vehicles([replace(v,vin='WBA12345678901235',url=v.url+'-other',price_lakh=40),
                     replace(v,vin='WBA12345678901236',url=v.url+'-third',price_lakh=50)])
    rows,_=search_inventory()
    target=next(row for row in rows if row['price_lakh']==30)
    selected,_=search_inventory(_vehicle_ids=[target['vehicle_id']],require_persistence=True)
    assert len(selected)==1
    assert selected[0]['comp_median']==target['comp_median']==40
    assert selected[0]['comparable_count']==3
    ingest_vehicles([replace(v,sold_signal=True,live_verified=False)])
    assert search_inventory(_vehicle_ids=[target['vehicle_id']],require_persistence=True)[0]==[]


@pytest.mark.parametrize('initial,current,filters',[(30,45,{'budget_max':40}),(45,30,{'budget_min':40})])
def test_budget_cannot_select_an_older_qualifying_price(db,initial,current,filters):
    v=ingest(db,price_lakh=initial)
    ingest_vehicles([replace(v,price_lakh=current)])
    rows,sources,count=search_inventory(query='BMW X1',condition='used',return_count=True,**filters)
    assert rows==[] and sources==[] and count==0
    rows,_=search_inventory(query='BMW X1',condition='used')
    assert len(rows)==1 and rows[0]['price_lakh']==current


def test_model_search_matches_trim_and_hyphenated_tokens_without_substrings(db):
    v=ingest(db,model='X5 xDrive40i M-Sport',title='BMW X5',vin=None)
    ingest_vehicles([replace(v,model='X50',title='BMW X50',url='https://fixture.invalid/x50')])
    rows,sources,count=search_inventory(query='BMW X5',return_count=True)
    assert count==1 and rows[0]['model']=='X5 xDrive40i M-Sport'
    assert sources[0]['listings_found']==1
    rows,_=search_inventory(query='BMW M Sport')
    assert len(rows)==1


def test_runtime_config_repair_preserves_governance_and_existing_settings(db):
    from src.source_runtime_config import restore_config
    sid=add_source(db)
    db.execute("update public.sources set enabled=false,adapter_status='candidate',metadata=%s::jsonb where source_id=%s",
               (json.dumps({'query_url_template':'https://custom.invalid','operator_note':'keep'}),sid))
    db.commit()
    source={'name':'Fixture Dealer','parser_strategy':'bbt_cards',
            'query_url_template':'https://seed.invalid',
            'endpoints':[{'url':'https://fixture.invalid/demo','condition':'demo'}]}
    assert restore_config([source],apply=False)
    assert db.execute('select metadata from public.sources where source_id=%s',(sid,)).fetchone()['metadata'].get('parser_strategy') is None
    restore_config([source],apply=True)
    row=db.execute('select * from public.sources where source_id=%s',(sid,)).fetchone()
    assert row['enabled'] is False and row['adapter_status']=='candidate'
    assert row['metadata']['parser_strategy']=='bbt_cards'
    assert row['metadata']['query_url_template']=='https://custom.invalid'
    assert row['metadata']['operator_note']=='keep'
    assert restore_config([source],apply=True)==[]


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


def test_baseline_refresh_covers_non_example_brands_and_all_marketplaces(db,monkeypatch):
    monkeypatch.setattr('src.inventory_refresh_planner.CAR_MAKES',['Audi','Toyota','Hyundai'])
    first = add_source(db, 'National Marketplace')
    second = add_source(db, 'Second Marketplace')
    db.execute("update public.source_capabilities set capability_value='all'")
    for brand in ('Audi', 'Toyota', 'Hyundai'):
        db.execute("insert into public.source_capabilities(source_id,capability_type,capability_value) values (%s,'brand',%s)",(first,brand))
    db.commit()
    # Restore the production function rather than the single-job fixture stub.
    monkeypatch.setattr('src.inventory_refresh_planner.baseline_brand_demands',baseline_brand_demands)
    monkeypatch.setattr('src.inventory_refresh_planner.load_search_demand',lambda **kwargs:[])
    assert schedule_refreshes()==8  # global + each brand, on both sources
    db.commit()
    rows=db.execute("select source_id,brand from public.inventory_refresh_queue").fetchall()
    assert {(r['source_id'],r['brand']) for r in rows}=={(s,b) for s in (first,second) for b in ('','audi','hyundai','toyota')}


def test_partial_inventory_paginates_without_repricing_comparison_cohort(db,monkeypatch):
    add_source(db)
    cars=[vehicle(vin='WBA1234567890123'+str(i),url='https://fixture.invalid/car/'+str(i),price_lakh=price) for i,price in enumerate([20,30,40])]
    assert ingest_vehicles(cars)['observations']==3
    first=post_search(monkeypatch,{'query':'BMW X1','page_size':1},['Fixture Dealer','Missing Dealer'])
    assert first['mode']=='inventory_partial'
    assert first['total_results']==3 and first['has_more']
    assert first['results'][0]['comp_median']==30
    assert first['results'][0]['comparable_count']==3
    assert first['results'][0]['discount_pct']==33.3
    last=post_search(monkeypatch,{'query':'BMW X1','page_size':1,'page':3},['Fixture Dealer','Missing Dealer'])
    assert not last['has_more'] and last['total_results']==3
    assert last['results'][0]['comp_median']==30
    rows, sources, total=search_inventory(query='BMW X1',limit=1,offset=99,return_count=True)
    assert rows==[] and sources==[] and total==3


def test_search_reports_every_planned_source_including_missing_inventory(db,monkeypatch):
    add_source(db)
    ingest_vehicles([vehicle()])
    names=['Fixture Dealer']+[f'Missing marketplace {i}' for i in range(20)]
    payload=post_search(monkeypatch,{'query':'BMW'},names)
    assert [s['name'] for s in payload['source_plan']]==names
    assert payload['mode']=='inventory_partial'


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
    assert db.execute("select model from public.inventory_refresh_queue where status='queued'").fetchone()['model']=='x1'


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
    assert run_cycle(10)=={'scheduled':1,'completed':1,'failed':0,'lifecycle':{'expired':0,'enrolled':0,'recovered':0,'heartbeat_gap_seconds':None}}
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


def test_continuation_is_persisted_fenced_and_resumed(db,monkeypatch):
    add_source(db)
    schedule_refreshes()
    first=claim_jobs(1)[0]
    cursor={'pending_urls':['https://fixture.invalid/page-2'],'visited_urls':['https://fixture.invalid/catalog']}
    complete_job(first['refresh_id'],success=True,attempt_count=first['attempt_count'],continuation=cursor,pages_fetched=1)
    row=db.execute('select * from public.inventory_refresh_queue where refresh_id=%s',(first['refresh_id'],)).fetchone()
    assert row['status']=='queued' and row['metadata']['continuation']==cursor
    assert 'last_success_at' not in row['metadata']
    second=claim_jobs(1)[0]
    assert second['attempt_count']>first['attempt_count']
    complete_job(first['refresh_id'],success=True,attempt_count=first['attempt_count'])
    assert db.execute('select status from public.inventory_refresh_queue where refresh_id=%s',(first['refresh_id'],)).fetchone()['status']=='running'
    requests=[]
    def fetch(adapter,request):
        requests.append(request)
        return AdapterResult(adapter.source_name,[],status='live',pages_fetched=1)
    monkeypatch.setattr('src.source_adapters.BuiltinMarketplaceAdapter.fetch',fetch)
    process_job(second)
    assert requests[0].continuation==cursor
    row=db.execute('select * from public.inventory_refresh_queue where refresh_id=%s',(first['refresh_id'],)).fetchone()
    assert row['status']=='completed' and row['metadata']['pages_fetched']==2
    assert 'continuation' not in row['metadata'] and row['metadata']['last_success_at']


def test_continuation_retry_budget_counts_failures_since_last_batch(db):
    add_source(db)
    schedule_refreshes()
    job=claim_jobs(1)[0]
    cursor={'pending_urls':['https://fixture.invalid/page-9'],'visited_urls':[]}
    db.execute("update public.inventory_refresh_queue set attempt_count=8 where refresh_id=%s",(job['refresh_id'],));db.commit()
    complete_job(job['refresh_id'],success=True,attempt_count=8,continuation=cursor,pages_fetched=8)
    failed=claim_jobs(1)[0]
    assert failed['attempt_count']==9
    complete_job(failed['refresh_id'],success=False,error='offline',attempt_count=9)
    db.execute("update public.inventory_refresh_queue set completed_at=now()-interval '1 day' where refresh_id=%s",(job['refresh_id'],));db.commit()
    assert recover_jobs()==1
    retried=claim_jobs(1)[0]
    assert retried['metadata']['continuation']==cursor and retried['attempt_count']==10


def test_oem_transport_to_persisted_resume_ingestion_and_index(db, monkeypatch):
    from urllib.parse import parse_qs
    source_id = add_source(db, 'Fixture OEM')
    url = 'https://www.mercedes-benzusedcar.in/buy-used-cars'
    db.execute("update public.sources set url=%s,metadata=%s::jsonb where source_id=%s",
               (url, json.dumps({'parser_strategy': 'mercedes_inventory'}), source_id))
    db.execute("update public.source_capabilities set capability_value='Mercedes-Benz' where source_id=%s", (source_id,))
    db.commit()
    html = Path('tests/fixtures/mercedes_demo_cards.html').read_text(encoding='utf-8')
    groups = []
    class Response:
        def __init__(self, text): self.text = text
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return self.text.encode()
    class Opener:
        def open(self, request, timeout):
            if request.data is None:
                return Response(json.dumps({'details': dict(security_token1='session-only', security_token2='two', security_token2_rand='three')}))
            fields = parse_qs(request.data.decode())
            if 'group_no' not in fields:
                return Response(html + '<input id="tr_load" value="1"><input id="total_groups" value="3">')
            group = int(fields['group_no'][0])
            groups.append(group)
            return Response(html.replace('.html', f'-group-{group}.html'))
    monkeypatch.setattr('src.oem_inventory.urllib.request.build_opener', lambda *args: Opener())
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE', '2')
    schedule_refreshes()
    first = claim_jobs(1)[0]
    assert process_job(first)['observations'] == 4
    row = db.execute('select * from public.inventory_refresh_queue where refresh_id=%s', (first['refresh_id'],)).fetchone()
    assert row['status'] == 'queued'
    assert row['metadata']['continuation']['oem_cursors'][url] == {'next_group': 2}
    assert 'session-only' not in json.dumps(row['metadata'])
    second = claim_jobs(1)[0]
    assert process_job(second)['observations'] == 2
    row = db.execute('select * from public.inventory_refresh_queue where refresh_id=%s', (first['refresh_id'],)).fetchone()
    assert row['status'] == 'completed' and row['metadata']['pages_fetched'] == 3
    assert groups == [1, 2]
    assert db.execute('select count(*) as n from public.listings').fetchone()['n'] == 6
    db.commit()
    payload = post_search(monkeypatch, {'query': 'Mercedes-Benz', 'condition': 'demo'}, ['Fixture OEM'])
    assert payload['results'] and all(row['brand'] == 'Mercedes-Benz' for row in payload['results'])


def test_elastic_revision_fences_price_sold_and_disabled_sources(db, monkeypatch):
    from src import elastic_inventory as elastic
    v = ingest(db)
    row = search_inventory(query='BMW X1')[0][0]
    now = datetime.now(timezone.utc)
    rev = elastic.revision(db)
    db.commit()
    manifest = dict(schema=1, revision=rev, year=now.year, generation='fixture',
                    expire_minutes=10080, valid_until=(now+timedelta(hours=1)).isoformat())
    def provider(method, path, *args, **kwargs):
        if path == '/_doc/manifest':
            return {'_source': manifest}
        return {'hits': {'total': {'value': 1, 'relation': 'eq'}, 'hits': [
            {'_source': {'vehicle_id': row['vehicle_id'], 'key': elastic.key_of(row)}}]}}
    monkeypatch.setattr(elastic, 'request', provider)
    monkeypatch.setenv('CARSCANNER_SEARCH_ENGINE', 'elasticsearch')
    monkeypatch.setattr(elastic, '_retry_after', 0)
    assert elastic.search_inventory(query='BMW X1', return_count=True)[2] == 1
    assert elastic.backend() == 'elasticsearch'
    ingest_vehicles([replace(v, price_lakh=45)])
    assert elastic.search_inventory(query='BMW X1', budget_max=40, return_count=True)[2] == 0
    assert elastic.backend() == 'postgresql'
    monkeypatch.setattr(elastic, '_retry_after', 0)
    ingest_vehicles([replace(v, sold_signal=True, live_verified=False)])
    assert elastic.search_inventory(query='BMW X1', return_count=True)[2] == 0
    assert elastic.backend() == 'postgresql'
    monkeypatch.setattr(elastic, '_retry_after', 0)
    db.execute('update public.sources set enabled=false')
    db.commit()
    assert elastic.search_inventory(query='BMW X1', return_count=True)[2] == 0
    assert elastic.backend() == 'postgresql'
    # Rollbacks also roll back invalidation; readers never see uncommitted data.
    before = elastic.revision(db)
    db.execute('update public.sources set enabled=true')
    assert elastic.revision(db) > before
    db.rollback()
    assert elastic.revision(db) == before
    db.commit()


def test_elastic_failed_bulk_does_not_publish_generation(db, monkeypatch):
    from src import elastic_inventory as elastic
    ingest(db)
    calls = []
    def provider(method, path, *args, **kwargs):
        calls.append((method, path))
        return {'errors': True} if '/_bulk' in path else {}
    monkeypatch.setattr(elastic, 'request', provider)
    with pytest.raises(elastic.IndexUnavailable, match='not published'):
        elastic.rebuild()
    assert any('/_bulk' in path for _, path in calls)
    assert not any('/_doc/manifest' in path for _, path in calls)


def test_shared_registry_cache_cannot_hide_price_updates_or_disabled_sources(db, monkeypatch):
    url = os.getenv('CARSCANNER_TEST_REDIS_URL')
    if not url: pytest.skip('Disposable Redis is required')
    from urllib.parse import urlsplit
    assert urlsplit(url).hostname in {'127.0.0.1', 'localhost', '::1'}
    monkeypatch.setenv('CARSCANNER_REDIS_URL', url)
    v = ingest(db)
    initial = post_search(monkeypatch, {'query': 'BMW X1', 'condition': 'used'}, ['Fixture Dealer'])
    assert initial['results'][0]['price_lakh'] == 30
    ingest_vehicles([replace(v, price_lakh=45)])
    current = post_search(monkeypatch, {'query': 'BMW X1', 'condition': 'used'}, ['Fixture Dealer'])
    assert current['results'][0]['price_lakh'] == 45
    db.execute('update public.sources set enabled=false')
    db.commit()
    disabled = post_search(monkeypatch, {'query': 'BMW X1', 'condition': 'used'}, ['Fixture Dealer'])
    assert disabled['results'] == []


def test_whole_index_refinements_and_ordering_precede_pagination(db):
    source=add_source(db)
    records=[vehicle(url=f'https://fixture.invalid/whole/{i}',vin=f'WBA{i:014d}',
                     price_lakh=10+i/10,fuel='diesel' if i<55 else 'petrol',
                     transmission='Automatic',mileage_km=100000-i*1000,
                     body_type='suv',owner_count=1) for i in range(65)]
    ingest_vehicles(records)
    rows,sources,total,summary=search_inventory(query='BMW',fuels=['petrol'],
        transmissions=['automatic'],body_types=['suv'],max_mileage_km=46000,
        limit=3,sort='km',return_count=True,with_summary=True)
    assert total==10
    assert [r['km'] for r in rows]==[36000,37000,38000]
    assert summary['result_count']==10
    assert summary['sources']==['Fixture Dealer']
    next_rows,_,next_total=search_inventory(query='BMW',fuels=['petrol'],
        transmissions=['automatic'],body_types=['suv'],max_mileage_km=46000,
        limit=3,offset=3,sort='km',return_count=True)
    assert next_total==10 and [r['km'] for r in next_rows]==[39000,40000,41000]
    assert not {r['vehicle_id'] for r in rows}&{r['vehicle_id'] for r in next_rows}
    # Restricting the buyer's budget must not change the comparison reference.
    cheap,_,_=search_inventory(query='BMW',budget_max=11,return_count=True)
    assert cheap and all(r['comparable_count']==65 for r in cheap)
    assert all(float(r['comp_median'])==13.2 for r in cheap)


def test_ai_daily_quota_is_atomic_and_durable(db,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from src.buyer_ai import reserve_call, AIUnavailable
    db.execute('truncate public.buyer_ai_daily_usage');db.commit()
    monkeypatch.setenv('CARSCANNER_AI_DAILY_LIMIT','5')
    def attempt(_):
        try: reserve_call();return True
        except AIUnavailable:return False
    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes=list(executor.map(attempt,range(15)))
    assert sum(outcomes)==5
    assert db.execute('select calls from public.buyer_ai_daily_usage').fetchone()['calls']==5
    db.execute('set local role anon')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute('select * from public.buyer_ai_daily_usage')
    db.rollback()


def test_worker_gives_unserved_brands_a_turn_before_high_priority_continuations(db):
    source=add_source(db)
    for brand,priority,started in [('bmw',100,True),('hyundai',8,False),('skoda',8,False)]:
        db.execute("""insert into inventory_refresh_queue(source_id,brand,priority,started_at)
            values (%s,%s,%s,case when %s then now() else null end)""",(source,brand,priority,started))
    db.commit()
    first=claim_jobs(1)[0]
    assert first['brand'] in {'hyundai','skoda'}
    complete_job(first['refresh_id'],success=True,attempt_count=first['attempt_count'],continuation={'pending_urls':['https://fixture.invalid/page2']})
    second=claim_jobs(1)[0]
    assert {first['brand'],second['brand']}=={'hyundai','skoda'}


def test_scheduler_preserves_queue_age_and_normalizes_demand_keys(db,monkeypatch):
    add_source(db)
    db.execute("update source_capabilities set capability_value='all'");db.commit()
    monkeypatch.setattr('src.inventory_refresh_planner.load_search_demand',lambda **kwargs:[
        {'brand':'Honda','model':'City','condition':'used'}, {'brand':'honda','model':'city','condition':'used'}])
    schedule_refreshes()
    db.execute("update inventory_refresh_queue set requested_at=now()-interval '3 days'");db.commit()
    before=db.execute('select refresh_id,requested_at from inventory_refresh_queue order by refresh_id').fetchall();db.commit()
    schedule_refreshes()
    after=db.execute('select refresh_id,requested_at from inventory_refresh_queue order by refresh_id').fetchall()
    assert after==before and len(after)==2
    assert db.execute("select brand,model from inventory_refresh_queue where brand<>''").fetchone()=={'brand':'honda','model':'city'}


def test_national_sweep_excludes_local_and_model_demand(db):
    source=add_source(db)
    for brand,model,state,priority in [('tata','nexon','',100),('tata','','delhi',100),('tata','','',1)]:
        db.execute("""insert into inventory_refresh_queue(source_id,brand,model,destination_state,priority)
            values (%s,%s,%s,%s,%s)""",(source,brand,model,state,priority))
    db.commit()
    job=claim_jobs(1,baseline_only=True)[0]
    assert job['brand']=='tata' and job['model']=='' and job['destination_state']==''


@pytest.mark.parametrize('stored,query',[('MG Motor','MG'),('Citroën','Citroen')])
def test_make_aliases_find_current_inventory(db,stored,query):
    add_source(db)
    ingest_vehicles([vehicle(brand=stored,model='Test model')])
    assert search_inventory(query=query,condition='used',return_count=True)[2]==1


def test_discovered_models_fan_out_only_to_verified_model_adapters_and_resume(db):
    from src.used_inventory_frontier import enqueue_models,reschedule_models
    for name in ('A','B','Unverified'):
        add_source(db,name)
    db.execute("update sources set metadata=%s::jsonb",(json.dumps({'parser_strategy':'carwale_cards','query_url_template':'https://fixture.invalid/{model_slug}'}),))
    db.execute("update source_capabilities set capability_value='all'")
    db.execute("update source_adapters set status='draft' where source_id=(select source_id from sources where name='Unverified')")
    db.commit()
    evidence=[{'model':'Nano','discovery_kind':'used_catalog_link','evidence_url':'https://fixture.invalid/used/tata-nano/','advertised_count':200}]
    assert enqueue_models('Tata',evidence)==2
    first=claim_jobs(1,models_only=True)[0]
    assert first['model']=='nano' and first['destination_state']==''
    complete_job(first['refresh_id'],success=True,attempt_count=first['attempt_count'],continuation={'pending_urls':['https://fixture.invalid/page-2']})
    enqueue_models('Tata',evidence)
    resumed=claim_jobs(1,continuations_only=True)[0]
    assert resumed['refresh_id']==first['refresh_id']
    assert resumed['metadata']['continuation']['pending_urls']==['https://fixture.invalid/page-2']
    complete_job(resumed['refresh_id'],success=True,attempt_count=resumed['attempt_count'])
    assert reschedule_models()==0
    db.execute("update inventory_refresh_queue set metadata=jsonb_set(metadata,'{last_success_at}',to_jsonb((now()-interval '1 day')::text)) where status='completed'")
    db.commit()
    assert reschedule_models()==1
    assert enqueue_models('MG Motor',[{**evidence[0],'model':'Hector'}])==2
    assert db.execute("select distinct brand from inventory_refresh_queue where model='hector'").fetchall()==[{'brand':'mg'}]


def test_catalogue_reservation_and_saved_evidence(db):
    from src.catalog_traversal import wake_catalogues
    add_source(db, 'Catalogue')
    db.execute("update sources set metadata=%s::jsonb", (json.dumps({'city_catalog_path_pattern':'/used/[a-z-]+'}),))
    db.execute("insert into inventory_refresh_queue(source_id,brand,model,condition,destination_state,status) select source_id,'','','both','','completed' from sources")
    db.commit()
    assert wake_catalogues() == 1
    first = claim_jobs(1, catalogues_only=True)[0]
    evidence = {'coverage_state':'partial_traversal', 'visited_page_count':2}
    cursor = {'pending_urls':['https://fixture.invalid/used/pune']}
    complete_job(first['refresh_id'], success=True, attempt_count=first['attempt_count'],
                 continuation=cursor, pages_fetched=2, scan_evidence=evidence)
    assert wake_catalogues() == 0
    resumed = claim_jobs(1, catalogues_only=True)[0]
    assert resumed['metadata']['last_scan_evidence'] == evidence
    assert resumed['metadata']['continuation'] == cursor


def test_historical_model_bootstrap_never_restores_expired_inventory(db):
    from src.used_inventory_frontier import seed_observed_models
    add_source(db)
    db.execute("update sources set metadata=%s::jsonb",(json.dumps({'parser_strategy':'cardekho_cards','query_url_template':'https://fixture.invalid/{model_slug}'}),))
    db.execute("update source_capabilities set capability_value='all'");db.commit()
    ingest_vehicles([vehicle(brand='Ford',model='Fiesta')])
    db.execute("update listings set last_verified_at=now()-interval '30 days'");db.commit()
    assert seed_observed_models()==1
    job=db.execute("select brand,model,metadata from inventory_refresh_queue where model='fiesta'").fetchone()
    assert job['brand']=='ford' and job['metadata']['model_discovery']['evidence_url']
    assert search_inventory(query='Ford Fiesta',condition='used',return_count=True)[2]==0


def test_observed_model_metadata_survives_expired_stock_without_restoring_it(db):
    from api.catalog import observed_models
    ingest(db,brand='Jaguar',model='F-Pace')
    db.execute("update listings set last_verified_at=now()-interval '30 days'");db.commit()
    assert observed_models('Jaguar')==[{'name':'F-Pace','slug':'f-pace','catalog_verified':'observed_inventory'}]
    assert observed_models('Honda')==[]
    assert search_inventory(query='Jaguar F-Pace',return_count=True)[2]==0


def old_renewal(db,condition='used'):
    from src.inventory_lifecycle import maintain,claim
    v=ingest(db,condition_signal=condition,source_listing_id='stock-1')
    db.execute("update listings set last_verified_at=now()-interval '8 hours'")
    db.commit();maintain()
    return v,claim(condition)


def test_lifecycle_expiry_uses_source_and_demo_policy_without_deleting_history(db):
    from src.inventory_lifecycle import maintain
    add_source(db)
    ingest_vehicles([vehicle(condition_signal=c,url='https://fixture.invalid/'+c,vin=None) for c in ['used','demo']])
    db.execute("update listings set last_verified_at=now()-interval '36 hours'");db.commit()
    assert search_inventory(condition='used',return_count=True)[2]==1
    assert search_inventory(condition='demo',return_count=True)[2]==0
    assert maintain()['expired']==1
    assert db.execute('select count(*) as n from vehicle_observations').fetchone()['n']==2
    db.execute('update sources set expire_after_minutes=60');db.commit()
    assert search_inventory(condition='used',return_count=True)[2]==0
    assert maintain()['expired']==1


def test_maintenance_does_not_apply_stricter_used_cap_to_demo(db,monkeypatch):
    from src.inventory_lifecycle import maintain
    monkeypatch.setenv('CARSCANNER_USED_EXPIRE_MINUTES','60')
    monkeypatch.setenv('CARSCANNER_DEMO_EXPIRE_MINUTES','1440')
    add_source(db)
    ingest_vehicles([vehicle(condition_signal=c,url='https://fixture.invalid/'+c,vin=None) for c in ['used','demo']])
    db.execute("update listings set last_verified_at=now()-interval '2 hours'");db.commit()
    assert maintain()['expired']==1
    assert search_inventory(condition='demo',return_count=True)[2]==1


def test_listing_renewal_updates_price_preserves_condition_and_history(db):
    from src.inventory_lifecycle import finish
    v,job=old_renewal(db,'demo')
    assert finish(job,{'outcome':'available','price_lakh':25,'availability':'InStock'})
    rows,_,total=search_inventory(condition='demo',return_count=True)
    assert total==1 and rows[0]['price_lakh']==25
    assert db.execute('select count(*) as n from vehicle_observations').fetchone()['n']==2
    assert db.execute('select last_outcome,status from inventory_listing_refresh').fetchone()=={'last_outcome':'available','status':'completed'}


def test_unconfirmed_demo_condition_is_quarantined_without_sold_or_history_deletion(db):
    from src.inventory_lifecycle import finish
    _,job=old_renewal(db,'demo')
    finish(job,{'outcome':'condition_unverified','availability':'InStock'})
    assert search_inventory(condition='demo',return_count=True)[2]==0
    assert db.execute('select status from listings').fetchone()['status']=='stale'
    assert db.execute('select count(*) as n from vehicle_observations').fetchone()['n']==1


def test_lost_lease_and_newer_positive_evidence_fence_stale_renewal(db):
    from src.inventory_lifecycle import finish,claim
    v,job=old_renewal(db)
    db.execute("update inventory_listing_refresh set lease_token=gen_random_uuid()");db.commit()
    assert not finish(job,{'outcome':'unavailable'})
    assert search_inventory(return_count=True)[2]==1
    db.execute("update inventory_listing_refresh set status='queued',due_at=now()");db.commit()
    job=claim('used')
    ingest_vehicles([replace(v,price_lakh=45)])
    assert finish(job,{'outcome':'unavailable'})
    rows,_=search_inventory()
    assert rows[0]['price_lakh']==45
    assert db.execute('select last_outcome from inventory_listing_refresh').fetchone()['last_outcome']=='superseded'


def test_consecutive_404s_are_required_and_network_errors_reset_the_sequence(db):
    from src.inventory_lifecycle import finish,claim
    _,job=old_renewal(db)
    finish(job,{'outcome':'missing','http_status':404})
    assert db.execute('select status from listings').fetchone()['status']=='active'
    assert db.execute("select due_at>now()+interval '59 minutes' as delayed from inventory_listing_refresh").fetchone()['delayed']
    for evidence in [{'outcome':'error'}, {'outcome':'missing','http_status':404}, {'outcome':'missing','http_status':404}]:
        db.execute('update inventory_listing_refresh set due_at=now()');db.commit()
        finish(claim('used'),evidence)
    assert db.execute('select status from listings').fetchone()['status']=='removed'
    assert search_inventory(return_count=True)[2]==0


def test_domain_lease_is_shared_and_stale_release_cannot_clear_new_owner(db):
    from src.crawl_leases import acquire,release
    first=acquire('https://fixture.invalid/catalogue')
    assert first and acquire('https://fixture.invalid/listing') is None
    db.execute("update inventory_crawl_leases set lease_expires_at=now()-interval '1 second'");db.commit()
    second=acquire('https://fixture.invalid/listing')
    assert second and first!=second
    release(first)
    assert acquire('https://fixture.invalid/') is None
    release(second)


def test_catalogue_renewal_resets_previous_missing_sequence(db):
    from src.inventory_lifecycle import finish,claim
    _,job=old_renewal(db)
    finish(job,{'outcome':'missing','http_status':404})
    # Previous 404 was yesterday; a catalogue supplied positive evidence eight
    # hours ago. Today's first missing check must not combine with yesterday's.
    db.execute("update inventory_listing_refresh set last_checked_at=now()-interval '1 day',due_at=now()")
    db.execute("update listings set last_verified_at=now()-interval '8 hours'");db.commit()
    finish(claim('used'),{'outcome':'missing','http_status':404})
    assert db.execute('select status from listings').fetchone()['status']=='active'
    assert db.execute('select missing_count from inventory_listing_refresh').fetchone()['missing_count']==1


def test_catalogue_tombstone_uses_exact_url_and_cannot_override_newer_observation(db):
    from src.inventory_lifecycle import retire_catalogue_evidence
    v=ingest(db,source_listing_id='stock-1')
    evidence=[{'url':v.url,'reason':'booked','evidence_url':'https://fixture.invalid/catalog'}]
    before=datetime.now(timezone.utc)-timedelta(days=1)
    assert retire_catalogue_evidence(evidence,'Fixture Dealer',before,db)==0
    assert retire_catalogue_evidence(evidence,'Fixture Dealer',datetime.now(timezone.utc),db)==1
    db.commit()
    assert search_inventory(return_count=True)[2]==0


def test_reclaimed_catalogue_worker_cannot_write_observations(db,monkeypatch):
    add_source(db)
    db.execute("insert into inventory_refresh_queue(source_id) select source_id from sources");db.commit()
    job=claim_jobs(1)[0]
    def fetch(adapter,request):
        db.execute("update inventory_refresh_queue set status='queued'");db.commit()
        db.execute("update inventory_crawl_leases set lease_expires_at=now()-interval '1 second'");db.commit()
        assert claim_jobs(1)[0]['attempt_count']==job['attempt_count']+1
        return AdapterResult('Fixture Dealer',[{'brand':'BMW','model':'X1','url':'https://fixture.invalid/new',
            'price_lakh':30,'condition_signal':'used','live_verified':True}],status='live')
    monkeypatch.setattr('src.inventory_refresh_worker.BuiltinMarketplaceAdapter.fetch',fetch)
    assert process_job(job)=={'superseded':1}
    assert db.execute('select count(*) as n from vehicle_observations').fetchone()['n']==0


def test_demo_acquisition_has_its_own_verified_global_slot(db):
    for name in ['Used','Demo','Unverified']:
        add_source(db,name)
    db.execute("insert into source_capabilities(source_id,capability_type,capability_value) select source_id,'condition','demo' from sources where name in ('Demo','Unverified')")
    db.execute("update source_adapters set status='draft' where source_id=(select source_id from sources where name='Unverified')")
    db.execute("insert into inventory_refresh_queue(source_id,condition) select source_id,'demo' from sources");db.commit()
    jobs=claim_jobs(1,demo_only=True)
    assert len(jobs)==1 and jobs[0]['source_name']=='Demo'


def test_private_lifecycle_tables_have_no_browser_access(db):
    for table in ['inventory_listing_refresh','inventory_crawl_leases','inventory_pipeline_runs']:
        assert db.execute("select relrowsecurity from pg_class where oid=%s::regclass",('public.'+table,)).fetchone()['relrowsecurity']
        assert not db.execute("select has_table_privilege('anon',%s,'select') as allowed",('public.'+table,)).fetchone()['allowed']


def test_coverage_matrix_uses_latest_customer_eligibility_and_keeps_raw_location_evidence(db):
    from src.coverage_operations import operations_report
    v=ingest(db)
    before=operations_report()
    assert sum(r['eligible_offers'] for r in before['coverage_matrix'])==1
    assert before['coverage_matrix'][0]['seller_location_label']=='Delhi'
    db.execute("""insert into vehicle_observations(vehicle_id,listing_id,source_id,observed_at,
        live_verified,data_consistent,sold_signal,price_lakh,snapshot)
        select vehicle_id,listing_id,source_id,now()+interval '1 second',true,true,true,30,'{}'
        from listings""");db.commit()
    assert search_inventory(return_count=True)[2]==0
    after=operations_report()
    assert sum(r['eligible_offers'] for r in after['coverage_matrix'])==0
    assert sum(r['observed_offers'] for r in after['coverage_matrix'])==1
    assert not after['complete_market_coverage']
    assert after['coverage_matrix'][0]['exclusion_reasons']['sold_or_availability_unknown']==1


def test_seed_sync_preserves_operator_governance_and_reviewed_activation_is_explicit(db):
    from src.source_registry_db import sync_registry,source_key
    seed=dict(name='Fixture Seed',url='https://fixture.invalid/catalog',adapter_status='live',
        parser_strategy='seed-parser',brands=['BMW'],conditions=['used','demo'])
    assert sync_registry([seed])==1
    key=source_key(seed)
    db.execute("""update sources set enabled=false,adapter_status='candidate',
        metadata='{"parser_strategy":"operator-parser","operator_note":"paused"}'::jsonb
        where source_key=%s""",(key,))
    db.execute('update source_endpoints set is_active=false')
    db.execute("delete from source_capabilities where capability_type='condition' and capability_value='demo'")
    db.commit()
    assert sync_registry([{**seed,'new_missing_setting':'restored'}])==1
    row=db.execute('select * from sources where source_key=%s',(key,)).fetchone()
    assert not row['enabled'] and row['adapter_status']=='candidate'
    assert row['metadata']['parser_strategy']=='operator-parser'
    assert row['metadata']['operator_note']=='paused'
    assert row['metadata']['new_missing_setting']=='restored'
    assert not db.execute('select is_active from source_endpoints').fetchone()['is_active']
    assert not db.execute("select 1 from source_capabilities where capability_value='demo'").fetchone()
    db.commit()
    sync_registry([seed],reviewed_update=True)
    row=db.execute('select * from sources where source_key=%s',(key,)).fetchone()
    assert row['enabled'] and row['adapter_status']=='live'
    assert row['metadata']['parser_strategy']=='seed-parser'
    assert db.execute('select is_active from source_endpoints').fetchone()['is_active']


def test_coverage_diagnoses_expired_disabled_and_missing_observations_without_resurrecting(db):
    from src.coverage_operations import operations_report
    ingest(db)
    db.execute("update listings set last_verified_at=now()-interval '8 days'")
    db.execute('update sources set enabled=false')
    db.execute("insert into inventory_refresh_queue(source_id,requested_at) select source_id,now()-interval '12 hours' from sources")
    db.commit()
    report=operations_report()
    priority=report['source_priorities'][0]
    assert priority['exclusion_reasons']=={'source_disabled':1,'verification_expired_or_missing':1}
    assert priority['queued_jobs']==1 and priority['oldest_queued_hours']>=12
    assert priority['eligible_offers']==0 and search_inventory(return_count=True)[2]==0
    db.execute('delete from vehicle_observations');db.commit()
    report=operations_report()
    reasons=report['source_priorities'][0]['exclusion_reasons']
    assert reasons['observation_unverified_or_missing']==1
    assert reasons['price_invalid_or_missing']==1
    assert report['source_priorities'][0]['eligible_offers']==0


def test_unclassified_offers_are_reported_but_not_enrolled_for_condition_specific_renewal(db):
    from src.inventory_lifecycle import maintain
    from src.coverage_operations import operations_report
    ingest(db,condition_signal='unknown')
    maintain()
    assert db.execute('select count(*) as n from inventory_listing_refresh').fetchone()['n']==0
    result=operations_report()
    assert result['source_priorities'][0]['needs_classification']==1


def test_coverage_keeps_successful_batch_timestamp_when_a_later_attempt_fails(db):
    from src.coverage_operations import operations_report
    add_source(db)
    db.execute('insert into inventory_refresh_queue(source_id) select source_id from sources');db.commit()
    job=claim_jobs(1)[0]
    evidence={'pages_this_batch':2,'listings_this_batch':40,'coverage_state':'partial_traversal'}
    complete_job(job['refresh_id'],success=True,attempt_count=job['attempt_count'],
        continuation={'pending_urls':['https://fixture.invalid/page-3']},scan_evidence=evidence)
    stamp=db.execute("select metadata->>'last_batch_observed_at' as stamp from inventory_refresh_queue").fetchone()['stamp']
    assert stamp
    job=claim_jobs(1)[0]
    complete_job(job['refresh_id'],success=False,attempt_count=job['attempt_count'],error='fixture failure')
    result=operations_report()
    assert result['source_priorities'][0]['last_batch_yield']['measured_at']==stamp
    assert any(r['last_attempt_failed'] for r in result['declared_scopes'])


def test_source_probe_claims_survive_restarts_and_reject_stale_completion(db):
    from types import SimpleNamespace
    from src.source_registry_db import record_discoveries,load_probe_history,claim_source_probe,finish_source_probe
    item=SimpleNamespace(domain='fixture.invalid',url='https://fixture.invalid/new-catalogue')
    record_discoveries([vars(item)])
    first=claim_source_probe(item)
    assert first and claim_source_probe(item) is None
    history=load_probe_history([item.url])[item.url]
    assert history['last_probe_at'] and history['probe_result']['status']=='running'
    db.execute("update source_discoveries set last_probe_at=now()-interval '31 minutes'");db.commit()
    second=claim_source_probe(item)
    assert second and second!=first
    assert not finish_source_probe(item,first,{'status':'rejected'})
    assert finish_source_probe(item,second,{'status':'rejected','listings_found':0})
    assert not finish_source_probe(item,second,{'status':'validated'})
    assert load_probe_history([item.url])[item.url]['probe_result']['status']=='rejected'


def test_source_discovery_stages_new_endpoint_without_activating_it_or_existing_adapter(db):
    from src.source_registry_db import record_discoveries,promote_discovery,claim_source_probe
    from types import SimpleNamespace
    source_id=add_source(db)
    item=dict(domain='fixture.invalid',url='https://fixture.invalid/new-catalogue')
    record_discoveries([item])
    assert promote_discovery(item,listings_found=2)=='Fixture Dealer'
    endpoint=db.execute('select is_active,metadata from source_endpoints where source_id=%s and url=%s',
        (source_id,item['url'])).fetchone()
    assert not endpoint['is_active'] and endpoint['metadata']['requires_adapter_verification']
    assert db.execute("select count(*) as n from source_adapters where status='verified'").fetchone()['n']==1
    assert claim_source_probe(SimpleNamespace(**item)) is None
    db.execute('update source_endpoints set is_active=true where url=%s',(item['url'],));db.commit()
    promote_discovery(item,listings_found=2)
    assert db.execute('select is_active from source_endpoints where url=%s',(item['url'],)).fetchone()['is_active']


def test_reviewed_oem_resume_reaches_canonical_search_without_persisting_session(db,monkeypatch):
    import io
    from urllib.parse import parse_qs
    from src import reviewed_inventory
    add_source(db,'Skoda Certified Pre-Owned')
    db.execute("update sources set url='https://www.skodapreowned.in/buy',metadata=%s::jsonb",
        (json.dumps({'parser_strategy':'skoda_cards'}),))
    db.execute("update source_capabilities set capability_value='all'")
    db.execute('insert into inventory_refresh_queue(source_id) select source_id from sources');db.commit()
    first=Path('tests/fixtures/reviewed_skoda.html').read_text(encoding='utf-8')
    second=Path('tests/fixtures/reviewed_skoda_page2.json').read_text(encoding='utf-8')
    class PublicSession:
        def open(self,request,timeout):
            body=first if request.data is None else json.dumps({'stock':first}) if parse_qs(request.data.decode())['move_page']==['1'] else second
            return io.BytesIO(body.encode())
    original=reviewed_inventory.fetch_skoda_inventory
    monkeypatch.setattr(reviewed_inventory,'fetch_skoda_inventory',lambda *a,**kw:original(*a,**kw,opener=PublicSession()))
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE','1')
    assert process_job(claim_jobs(1)[0])['listings']==2
    checkpoint=db.execute('select metadata from inventory_refresh_queue').fetchone()['metadata']
    assert 'fixture-token' not in json.dumps(checkpoint)
    assert checkpoint['continuation']['oem_cursors']['https://www.skodapreowned.in/buy']=={'next_page':2}
    assert process_job(claim_jobs(1)[0])['listings']==2
    rows,_,total=search_inventory(condition='used',return_count=True)
    assert total==4 and all(row['source']=='Skoda Certified Pre-Owned' for row in rows)
    assert search_inventory(condition='demo',return_count=True)[2]==0


def test_global_catalogue_source_does_not_duplicate_whole_scans_for_each_buyer_intent(db,monkeypatch):
    add_source(db)
    db.execute("update sources set metadata=%s::jsonb",(json.dumps({'global_catalogue_only':True}),))
    db.execute("update source_capabilities set capability_value='all'");db.commit()
    monkeypatch.setattr('src.inventory_refresh_planner.baseline_brand_demands',lambda:[
        dict(brand='Honda',model='City',condition='used',destination_state='Karnataka'),
        dict(brand='BMW',model='',condition='both',destination_state='')])
    assert schedule_refreshes()==1
    job=db.execute('select brand,model,condition,destination_state from inventory_refresh_queue').fetchone()
    assert dict(job)==dict(brand='',model='',condition='both',destination_state='')


@pytest.mark.skipif(os.name=='nt',reason='Gunicorn requires Unix; WSGI adapter tests run on Windows')
def test_production_gunicorn_serves_real_indexed_inventory_and_shuts_down(db,disposable_database,tmp_path):
    import signal
    import socket
    import subprocess
    import sys
    import time
    ingest(db)
    db.commit()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0))
        port=probe.getsockname()[1]
    env={**os.environ,'SOURCE_INTELLIGENCE_DATABASE_URL':make_conninfo(disposable_database,application_name='carscanner_gunicorn_test'),
        'HOST':'127.0.0.1','PORT':str(port),'CARSCANNER_WEB_WORKERS':'1',
        'CARSCANNER_WEB_THREADS':'4','CARSCANNER_QUERY_DISCOVERY':'false','CARSCANNER_SEARCH_ENGINE':'postgresql'}
    base=f'http://127.0.0.1:{port}'
    with (tmp_path/'gunicorn.log').open('wb') as log:
        process=subprocess.Popen([sys.executable,'-m','gunicorn','--config','gunicorn.conf.py','wsgi:application'],
                                 env=env,stdout=log,stderr=log)
        try:
            deadline=time.monotonic()+20
            while True:
                assert process.poll() is None,'Gunicorn exited before readiness'
                try:
                    with urllib.request.urlopen(base+'/ready',timeout=3) as response:
                        assert json.load(response)['ok']
                    break
                except OSError:
                    if time.monotonic()>deadline:raise
                    time.sleep(.1)
            with urllib.request.urlopen(base+'//?qa=fixture',timeout=5) as response:
                assert b'id="brand"' in response.read()
                assert response.headers['X-CarScanner-Runtime']=='wsgi'
            req=urllib.request.Request(base+'/api/search',data=json.dumps({
                'query':'BMW X1','condition':'used','budget_max':35}).encode(),
                headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=10) as response:
                payload=json.load(response)
                assert response.headers['X-CarScanner-Runtime']=='wsgi'
            assert payload['ok'] and payload['search_engine']=='postgresql'
            assert payload['total_results']==1 and payload['results'][0]['price_lakh']==30
            assert payload['mode'].startswith('inventory')
            # Hold an actual search query in flight, terminate the master, then
            # release the database lock. The worker must drain that response.
            from concurrent.futures import ThreadPoolExecutor
            def search_again():
                with urllib.request.urlopen(req,timeout=15) as response:
                    return json.load(response)
            db.execute('lock table public.listings in access exclusive mode')
            with ThreadPoolExecutor(max_workers=3) as executor:
                pending=[executor.submit(search_again) for _ in range(3)]
                deadline=time.monotonic()+5
                while True:
                    db.execute('select pg_stat_clear_snapshot()')
                    waiting=db.execute("""select count(*) as n from pg_stat_activity
                        where application_name='carscanner_gunicorn_test' and wait_event_type='Lock'""").fetchone()['n']
                    if waiting>=3:break
                    if time.monotonic()>deadline:
                        db.rollback()
                        raise AssertionError('Search did not reach the database lock')
                    time.sleep(.05)
                try:
                    with pytest.raises(urllib.error.HTTPError) as busy:
                        urllib.request.urlopen(req,timeout=3)
                    assert busy.value.code==503
                    assert busy.value.headers['Retry-After']=='1'
                    with urllib.request.urlopen(base+'/health',timeout=3) as response:
                        assert response.read()==b'ok'
                    process.send_signal(signal.SIGTERM)
                finally:
                    # Do not strand blocked HTTP threads if an assertion fails.
                    db.commit()
                assert all(future.result(timeout=10)['total_results']==1 for future in pending)
            assert process.wait(timeout=10)==0
        finally:
            db.rollback()
            if process.poll() is None:
                process.kill();process.wait(timeout=5)
