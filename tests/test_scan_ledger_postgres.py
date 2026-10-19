"""Adversarial ledger boundaries on a disposable, localhost-only database."""
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from tests.test_inventory_postgres import (
    db, disposable_database, add_source, vehicle, psycopg,
)
from src.inventory_ingestion import ingest_vehicles, AcceptedObservation
from src.inventory_refresh_worker import claim_jobs, process_job
from src.scan_contract import scan_scope, generation, outcome
from src.source_adapters import AdapterRequest, AdapterResult

pytestmark = pytest.mark.integration


def ledger():
    from src import scan_ledger
    return scan_ledger


def setup_claim(conn):
    source_id = add_source(conn)
    conn.execute('insert into inventory_refresh_queue(source_id) values(%s)', (source_id,))
    conn.commit()
    job = claim_jobs(1)[0]
    scope, fingerprint = scan_scope({'source_id': source_id},
        AdapterRequest(query='', continuation={}), ['https://fixture.invalid/catalog'])
    evidence = {**outcome(generation({}, fingerprint), pending=False, background=True),
                'scope': scope, 'pages_this_batch': 1}
    return source_id, job, evidence


def finish_with_observations(conn, source_id, job, evidence, rows=None):
    batch = ledger().prepare_batch(job, source_id, evidence, conn)
    assert not batch['already_committed']
    accepted = []
    ingest_vehicles(rows if rows is not None else [vehicle()],
                    _connection=conn, _accepted_observations=accepted)
    ledger().finish_batch(batch, accepted, evidence, None, conn)
    return batch, accepted


def test_exact_observation_membership_preserves_repeated_writes_and_rejects_parser_rows(db):
    source_id, job, evidence = setup_claim(db)
    row = vehicle()
    batch, accepted = finish_with_observations(db, source_id, job, evidence,
        [row, replace(row, price_lakh=31), replace(row, live_verified=False),
         replace(row, source_name='Unregistered'), replace(row, price_lakh=None)])
    db.commit()
    assert len(accepted) == 2
    assert accepted[0].listing_id == accepted[1].listing_id
    assert accepted[0].observation_id != accepted[1].observation_id
    members = db.execute('select source_id,listing_id,observation_id,evidence_kind '
        'from inventory_scan_memberships where batch_id=%s order by observation_id',
        (batch['batch_id'],)).fetchall()
    assert members == [dict(source_id=a.source_id, listing_id=a.listing_id,
                           observation_id=a.observation_id, evidence_kind=a.evidence_kind)
                       for a in accepted]
    counts = db.execute('select accepted_count,pages_fetched from inventory_scan_batches '
                        'where batch_id=%s', (batch['batch_id'],)).fetchone()
    assert counts == {'accepted_count': 2, 'pages_fetched': 1}


def test_rollback_removes_observations_generation_batch_and_membership(db):
    source_id, job, evidence = setup_claim(db)
    finish_with_observations(db, source_id, job, evidence)
    db.rollback()
    for table in ('vehicle_observations', 'inventory_scan_generations',
                  'inventory_scan_batches', 'inventory_scan_memberships'):
        assert db.execute('select count(*) as n from ' + table).fetchone()['n'] == 0
    # The claim was committed separately; retry can prepare and accept it again.
    batch, accepted = finish_with_observations(db, source_id, job, evidence)
    db.commit()
    assert accepted and batch['batch_id']


def test_duplicate_committed_claim_is_detected_before_repeat_ingestion(db):
    source_id, job, evidence = setup_claim(db)
    batch, _ = finish_with_observations(db, source_id, job, evidence)
    db.commit()
    again = ledger().prepare_batch(job, source_id, evidence, db)
    assert again['already_committed']
    assert again['batch_id'] == batch['batch_id']
    assert db.execute('select count(*) as n from vehicle_observations').fetchone()['n'] == 1
    assert db.execute('select count(*) as n from inventory_scan_memberships').fetchone()['n'] == 1


def test_generation_fingerprint_cannot_be_rebound_to_changed_scope(db):
    source_id, job, evidence = setup_claim(db)
    finish_with_observations(db, source_id, job, evidence)
    db.commit()
    scope, fingerprint = scan_scope({'source_id': source_id},
        AdapterRequest(query='Honda', continuation={}), ['https://fixture.invalid/catalog'])
    changed = {**evidence, 'scope': scope, 'scope_fingerprint': fingerprint}
    with pytest.raises((ValueError, psycopg.Error)):
        ledger().prepare_batch(job, source_id, changed, db)
    db.rollback()
    stored = db.execute('select scope_fingerprint from inventory_scan_generations '
        'where generation_id=%s', (evidence['generation_id'],)).fetchone()
    assert stored['scope_fingerprint'] == evidence['scope_fingerprint']


@pytest.mark.parametrize('flag', ['completeness_verified', 'absence_reconciliation_permitted'])
def test_claimed_completeness_and_absence_authority_are_rejected(db, flag):
    source_id, job, evidence = setup_claim(db)
    with pytest.raises((ValueError, psycopg.Error)):
        ledger().prepare_batch(job, source_id, {**evidence, flag: True}, db)
    db.rollback()
    assert db.execute('select count(*) as n from inventory_scan_generations').fetchone()['n'] == 0


def test_cross_source_membership_cannot_be_inserted_even_directly(db):
    source_id, job, evidence = setup_claim(db)
    batch, accepted = finish_with_observations(db, source_id, job, evidence)
    db.commit()
    other_source = add_source(db, 'Second Dealer')
    foreign = []
    ingest_vehicles([vehicle(source_name='Second Dealer')], _connection=db,
                    _accepted_observations=foreign)
    db.commit()
    assert len(foreign) == 1
    with pytest.raises(psycopg.Error):
        db.execute('insert into inventory_scan_memberships '
            '(batch_id,source_id,listing_id,observation_id,evidence_kind) values(%s,%s,%s,%s,%s)',
            (batch['batch_id'], source_id, foreign[0].listing_id,
             foreign[0].observation_id, 'positive'))
    db.rollback()
    assert db.execute('select count(*) as n from inventory_scan_memberships').fetchone()['n'] == 1
    assert other_source != source_id


def test_same_source_observation_cannot_be_attached_to_wrong_listing(db):
    source_id, job, evidence = setup_claim(db)
    batch, accepted = finish_with_observations(db, source_id, job, evidence)
    db.commit()
    other = []
    ingest_vehicles([vehicle(url='https://fixture.invalid/car/2', source_listing_id='second')],
                    _connection=db, _accepted_observations=other)
    db.commit()
    assert other[0].listing_id != accepted[0].listing_id
    with pytest.raises(psycopg.Error):
        db.execute('insert into inventory_scan_memberships '
            '(batch_id,source_id,listing_id,observation_id,evidence_kind) values(%s,%s,%s,%s,%s)',
            (batch['batch_id'], source_id, accepted[0].listing_id,
             other[0].observation_id, 'positive'))
    db.rollback()


def test_finishing_invalid_identity_does_not_publish_partial_membership(db):
    source_id, job, evidence = setup_claim(db)
    batch = ledger().prepare_batch(job, source_id, evidence, db)
    accepted = []
    ingest_vehicles([vehicle()], _connection=db, _accepted_observations=accepted)
    invalid = AcceptedObservation(source_id, uuid4(), accepted[0].observation_id, 'positive')
    with pytest.raises((ValueError, psycopg.Error)):
        ledger().finish_batch(batch, [*accepted, invalid], evidence, None, db)
    db.rollback()
    assert db.execute('select count(*) as n from inventory_scan_memberships').fetchone()['n'] == 0
    assert db.execute('select count(*) as n from vehicle_observations').fetchone()['n'] == 0


@pytest.mark.parametrize('flag', ['completeness_verified', 'absence_reconciliation_permitted'])
def test_database_itself_denies_generation_authority_escalation(db, flag):
    source_id, job, evidence = setup_claim(db)
    finish_with_observations(db, source_id, job, evidence)
    db.commit()
    with pytest.raises(psycopg.Error):
        db.execute('update inventory_scan_generations set ' + flag + '=true where generation_id=%s',
                    (evidence['generation_id'],))
    db.rollback()


def worker_result(evidence, continuation=None):
    return AdapterResult('Fixture Dealer', [{
        'brand': 'BMW', 'model': 'X1', 'url': 'https://fixture.invalid/new',
        'listing_name': 'BMW X1', 'mfg_year': 2024, 'price_lakh': 30,
        'condition_signal': 'used', 'live_verified': True,
    }], status='live', pages_fetched=1, scan_evidence=evidence,
       continuation=continuation)


def test_worker_failure_after_ingestion_rolls_back_ledger_and_retry_commits_checkpoint(db, monkeypatch):
    source_id, job, evidence = setup_claim(db)
    monkeypatch.setenv('CARSCANNER_SCAN_LEDGER_ENABLED', 'true')
    pending = {**evidence, 'terminal_reason': 'pending_pages', 'coverage_state': 'partial_traversal'}
    checkpoint = {'pending_urls': ['https://fixture.invalid/page-2'], 'scan_generation': {
        key: pending[key] for key in ('generation_id', 'scope_fingerprint', 'contract_version',
                                    'started_at', 'resumed_legacy_checkpoint')}}
    monkeypatch.setattr('src.inventory_refresh_worker.BuiltinMarketplaceAdapter.fetch',
                        lambda *_: worker_result(pending, checkpoint))
    original_finish = ledger().finish_batch
    def fail_after_write(batch, accepted, evidence, continuation, conn):
        original_finish(batch, accepted, evidence, continuation, conn)
        raise RuntimeError('failure after accepted membership')
    monkeypatch.setattr('src.scan_ledger.finish_batch', fail_after_write)
    with pytest.raises(RuntimeError, match='failure after accepted membership'):
        process_job(job)
    for table in ('vehicle_observations', 'inventory_scan_generations',
                  'inventory_scan_batches', 'inventory_scan_memberships'):
        assert db.execute('select count(*) as n from ' + table).fetchone()['n'] == 0
    failed = db.execute('select status,metadata from inventory_refresh_queue where refresh_id=%s',
                        (job['refresh_id'],)).fetchone()
    assert failed['status'] == 'failed'
    assert 'continuation' not in failed['metadata']
    db.execute("update inventory_refresh_queue set status='queued' where refresh_id=%s", (job['refresh_id'],))
    db.commit()
    monkeypatch.setattr('src.scan_ledger.finish_batch', original_finish)
    retry = claim_jobs(1)[0]
    assert retry['attempt_count'] > job['attempt_count']
    assert process_job(retry)['observations'] == 1
    state = db.execute('select status,metadata from inventory_refresh_queue where refresh_id=%s',
                        (job['refresh_id'],)).fetchone()
    assert state['status'] == 'queued'
    assert state['metadata']['continuation'] == checkpoint
    assert db.execute('select count(*) as n from inventory_scan_memberships').fetchone()['n'] == 1
    assert db.execute('select accepted_count,completed_at from inventory_scan_batches').fetchone()['completed_at']


def test_superseded_worker_cannot_publish_observations_or_ledger(db, monkeypatch):
    source_id, job, evidence = setup_claim(db)
    monkeypatch.setenv('CARSCANNER_SCAN_LEDGER_ENABLED', 'true')
    def supersede(*_):
        db.execute("update inventory_refresh_queue set status='queued' where refresh_id=%s", (job['refresh_id'],))
        db.execute("update inventory_crawl_leases set lease_expires_at=now()-interval '1 second'")
        db.commit()
        assert claim_jobs(1)[0]['attempt_count'] > job['attempt_count']
        return worker_result(evidence)
    monkeypatch.setattr('src.inventory_refresh_worker.BuiltinMarketplaceAdapter.fetch', supersede)
    assert process_job(job) == {'superseded': 1}
    for table in ('vehicle_observations', 'inventory_scan_generations',
                  'inventory_scan_batches', 'inventory_scan_memberships'):
        assert db.execute('select count(*) as n from ' + table).fetchone()['n'] == 0


def test_pending_generation_checkpoint_mismatch_rolls_back(db):
    source_id, job, evidence = setup_claim(db)
    pending = {**evidence, 'terminal_reason': 'pending_pages', 'coverage_state': 'partial_traversal'}
    batch = ledger().prepare_batch(job, source_id, pending, db)
    accepted = []
    ingest_vehicles([vehicle()], _connection=db, _accepted_observations=accepted)
    checkpoint = {'pending_urls': ['https://fixture.invalid/page-2'],
                  'scan_generation': {**pending, 'generation_id': str(uuid4())}}
    with pytest.raises(ValueError, match='Continuation generation mismatch'):
        ledger().finish_batch(batch, accepted, pending, checkpoint, db)
    db.rollback()
    assert db.execute('select count(*) as n from vehicle_observations').fetchone()['n'] == 0


@pytest.mark.parametrize('table', ['inventory_scan_generations', 'inventory_scan_batches',
                                   'inventory_scan_memberships'])
def test_ledger_rls_and_browser_roles_have_no_table_access(db, table):
    assert db.execute('select relrowsecurity from pg_class where oid=%s::regclass',
                      ('public.' + table,)).fetchone()['relrowsecurity']
    for role in ('anon', 'authenticated'):
        for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
            assert not db.execute('select has_table_privilege(%s,%s,%s) as allowed',
                (role, 'public.' + table, privilege)).fetchone()['allowed']
        # Check actual execution too; privilege denial precedes constraints.
        identity = 'generation_id' if table == 'inventory_scan_generations' else 'batch_id'
        statements = ('select * from public.' + table,
                      'insert into public.' + table + ' default values',
                      'update public.' + table + ' set ' + identity + '=' + identity,
                      'delete from public.' + table)
        for statement in statements:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with db.transaction():
                    db.execute('set local role ' + role)
                    db.execute(statement)


def test_successive_worker_batches_keep_generation_and_exact_membership(db, monkeypatch):
    source_id, first, evidence = setup_claim(db)
    monkeypatch.setenv('CARSCANNER_SCAN_LEDGER_ENABLED', 'true')
    pending = {**evidence, 'terminal_reason': 'pending_pages', 'coverage_state': 'partial_traversal'}
    checkpoint = {'pending_urls': ['https://fixture.invalid/page-2'], 'scan_generation': {
        key: pending[key] for key in ('generation_id', 'scope_fingerprint', 'contract_version',
                                    'started_at', 'resumed_legacy_checkpoint')}}
    requests = []
    def fetch(adapter, request):
        requests.append(request)
        return worker_result(pending, checkpoint) if len(requests) == 1 else worker_result(evidence)
    monkeypatch.setattr('src.inventory_refresh_worker.BuiltinMarketplaceAdapter.fetch', fetch)
    assert process_job(first)['observations'] == 1
    assert db.execute('select state from inventory_scan_generations').fetchone()['state'] == 'partial'
    db.commit()
    second = claim_jobs(1)[0]
    assert second['attempt_count'] > first['attempt_count']
    assert process_job(second)['observations'] == 1
    assert requests[1].continuation == checkpoint
    state = db.execute('select status,metadata from inventory_refresh_queue where refresh_id=%s',
                       (first['refresh_id'],)).fetchone()
    assert state['status'] == 'completed' and 'continuation' not in state['metadata']
    generations = db.execute('select generation_id,state,completeness_verified,absence_reconciliation_permitted '
                             'from inventory_scan_generations').fetchall()
    assert generations == [dict(generation_id=UUID(evidence['generation_id']),
        state='exhausted_unverified', completeness_verified=False, absence_reconciliation_permitted=False)]
    batches = db.execute('select batch_id,attempt_count,accepted_count,completed_at '
                         'from inventory_scan_batches order by attempt_count').fetchall()
    assert len(batches) == 2 and batches[0]['batch_id'] != batches[1]['batch_id']
    assert all(row['accepted_count'] == 1 and row['completed_at'] for row in batches)
    members = db.execute('select batch_id,listing_id,observation_id from inventory_scan_memberships').fetchall()
    assert len(members) == 2
    assert len({row['listing_id'] for row in members}) == 1
    assert len({row['observation_id'] for row in members}) == 2
