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
from src.inventory_ingestion import ingest_vehicles
from src.inventory_refresh_planner import schedule_refreshes
from src.inventory_refresh_worker import claim_jobs, process_job
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
