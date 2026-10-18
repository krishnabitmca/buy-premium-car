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
    # Newer verification of the expensive offer must not relabel t…8248 tokens truncated…_state,status) select source_id,'','','both','','completed' from sources")
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
