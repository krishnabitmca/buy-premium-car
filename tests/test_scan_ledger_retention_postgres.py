"""Retention must delete bounded audit history, never inventory or active work."""
import json

import pytest

from tests.test_inventory_postgres import db, disposable_database, psycopg
from tests.test_scan_ledger_postgres import setup_claim, finish_with_observations

pytestmark = pytest.mark.integration


def retain(conn, **kwargs):
    from src.scan_ledger_retention import retain_scan_ledger
    return retain_scan_ledger(_connection=conn, **kwargs)


def seed_old(conn):
    source_id, job, evidence = setup_claim(conn)
    batch, accepted = finish_with_observations(conn, source_id, job, evidence)
    conn.execute("update inventory_refresh_queue set status='completed' where refresh_id=%s", (job['refresh_id'],))
    conn.execute("update inventory_scan_generations set captured_at=now()-interval '90 days',"
                 " last_batch_at=now()-interval '90 days'")
    conn.execute("update inventory_scan_batches set claim_started_at=now()-interval '90 days',"
                 " completed_at=now()-interval '90 days'")
    conn.commit()
    return source_id, job, evidence, batch, accepted


def ledger_counts(conn):
    return tuple(conn.execute('select count(*) as n from ' + name).fetchone()['n']
        for name in ('inventory_scan_generations', 'inventory_scan_batches', 'inventory_scan_memberships'))


def canonical(conn):
    # Full row snapshots detect accidental status, timestamps or payload changes.
    return {name: conn.execute('select row_to_json(t)::text as row from ' + name +
                              ' t order by row_to_json(t)::text').fetchall()
            for name in ('vehicles', 'listings', 'vehicle_observations')}


def test_dry_run_keeps_old_ledger_and_all_canonical_rows(db):
    seed_old(db)
    before = canonical(db)
    result = retain(db)
    assert result['eligible_generations'] == 1
    assert result['eligible_batches'] == result['eligible_memberships'] == 1
    assert result['deleted_generations'] == result['deleted_batches'] == result['deleted_memberships'] == 0
    assert ledger_counts(db) == (1, 1, 1)
    assert canonical(db) == before


def test_apply_removes_only_old_ledger_and_rollback_restores_it(db):
    seed_old(db)
    before = canonical(db)
    retain(db, apply=True)
    assert ledger_counts(db) == (0, 0, 0)
    assert canonical(db) == before
    db.rollback()
    assert ledger_counts(db) == (1, 1, 1)
    assert canonical(db) == before
    retain(db, apply=True)
    db.commit()
    assert ledger_counts(db) == (0, 0, 0)
    assert canonical(db) == before


@pytest.mark.parametrize('field', ['captured_at', 'last_batch_at'])
def test_recent_generation_evidence_is_never_pruned(db, field):
    seed_old(db)
    db.execute('update inventory_scan_generations set ' + field + '=now()')
    db.commit()
    retain(db, apply=True)
    assert ledger_counts(db) == (1, 1, 1)


def test_recent_completed_batch_prevents_whole_generation_pruning(db):
    seed_old(db)
    db.execute('update inventory_scan_batches set completed_at=now()')
    db.commit()
    retain(db, apply=True)
    assert ledger_counts(db) == (1, 1, 1)


@pytest.mark.parametrize('status', ['queued', 'running'])
def test_nonterminal_queue_preserves_generation(db, status):
    _, job, *_ = seed_old(db)
    db.execute('update inventory_refresh_queue set status=%s where refresh_id=%s', (status, job['refresh_id']))
    db.commit()
    retain(db, apply=True)
    assert ledger_counts(db) == (1, 1, 1)


@pytest.mark.parametrize('continuation', [
    {'scan_generation': {'generation_id': 'placeholder'}}, {}, 'malformed',
])
def test_continuation_reference_or_malformed_checkpoint_is_conservatively_preserved(db, continuation):
    _, job, evidence, *_ = seed_old(db)
    if isinstance(continuation, dict) and continuation:
        continuation['scan_generation']['generation_id'] = evidence['generation_id']
    db.execute('update inventory_refresh_queue set metadata=jsonb_build_object(\'continuation\',%s::jsonb) '
                'where refresh_id=%s', (json.dumps(continuation), job['refresh_id']))
    db.commit()
    retain(db, apply=True)
    assert ledger_counts(db) == (1, 1, 1)


def test_incomplete_batch_prevents_pruning(db):
    seed_old(db)
    db.execute('update inventory_scan_batches set completed_at=null')
    db.commit()
    retain(db, apply=True)
    assert ledger_counts(db) == (1, 1, 1)


def test_old_abandoned_partial_history_can_expire_without_changing_inventory(db):
    seed_old(db)
    before = canonical(db)
    db.execute("update inventory_scan_generations set state='partial'")
    db.commit()
    retain(db, apply=True)
    assert ledger_counts(db) == (0, 0, 0)
    assert canonical(db) == before


@pytest.mark.parametrize('limits', [{'batch_limit': 1}, {'membership_limit': 1}])
def test_generation_exceeding_deletion_budget_is_not_partially_pruned(db, limits):
    from src.scan_ledger import prepare_batch, finish_batch
    from src.inventory_ingestion import ingest_vehicles
    from tests.test_inventory_postgres import vehicle
    source_id, job, evidence, *_ = seed_old(db)
    next_job = {**job, 'attempt_count': job['attempt_count'] + 1}
    batch = prepare_batch(next_job, source_id, evidence, db)
    accepted = []
    ingest_vehicles([vehicle()], _connection=db, _accepted_observations=accepted)
    finish_batch(batch, accepted, evidence, None, db)
    db.execute("update inventory_scan_generations set last_batch_at=now()-interval '90 days'")
    db.execute("update inventory_scan_batches set completed_at=now()-interval '90 days',"
                "claim_started_at=now()-interval '90 days'")
    db.commit()
    result = retain(db, apply=True, **limits)
    assert result['skipped']['oversized'] == 1
    assert ledger_counts(db) == (1, 2, 2)


def test_locked_queue_is_skipped_without_waiting_or_partial_delete(db, disposable_database):
    _, job, *_ = seed_old(db)
    with psycopg.connect(disposable_database) as holder:
        holder.execute('select refresh_id from inventory_refresh_queue where refresh_id=%s for update',
                        (job['refresh_id'],))
        db.execute("set local statement_timeout='2s'")
        retain(db, apply=True)
        assert ledger_counts(db) == (1, 1, 1)


def test_locked_generation_is_skipped_without_waiting_or_partial_delete(db, disposable_database):
    _, _, evidence, *_ = seed_old(db)
    with psycopg.connect(disposable_database) as holder:
        holder.execute('select generation_id from inventory_scan_generations where generation_id=%s for update',
                        (evidence['generation_id'],))
        db.execute("set local statement_timeout='2s'")
        retain(db, apply=True)
        assert ledger_counts(db) == (1, 1, 1)


def test_generation_limit_bounds_whole_generation_deletion(db):
    from uuid import uuid4
    source_id, job, evidence, *_ = seed_old(db)
    second_evidence = {**evidence, 'generation_id': str(uuid4())}
    finish_with_observations(db, source_id,
                            {**job, 'attempt_count': job['attempt_count'] + 1}, second_evidence)
    db.execute("update inventory_scan_generations set captured_at=now()-interval '90 days',"
                "last_batch_at=now()-interval '90 days'")
    db.execute("update inventory_scan_batches set completed_at=now()-interval '90 days',"
                "claim_started_at=now()-interval '90 days'")
    db.commit()
    before = canonical(db)
    result = retain(db, apply=True, generation_limit=1)
    assert result['deleted_generations'] == result['deleted_batches'] == result['deleted_memberships'] == 1
    assert ledger_counts(db) == (1, 1, 1)
    assert canonical(db) == before


@pytest.mark.parametrize('configuration', [{'retention_days': 0}, {'generation_limit': 0},
                                         {'batch_limit': -1}, {'membership_limit': True},
                                         {'candidate_limit': '50'}, {'apply': 'yes'}])
def test_invalid_retention_configuration_cannot_delete_rows(db, configuration):
    seed_old(db)
    with pytest.raises(ValueError):
        retain(db, **configuration)
    assert ledger_counts(db) == (1, 1, 1)


def test_successful_retention_restores_caller_transaction_timeouts(db):
    seed_old(db)
    db.execute("set local lock_timeout='750ms'")
    db.execute("set local statement_timeout='9s'")
    before = db.execute("select current_setting('lock_timeout') as lock_timeout,"
                        "current_setting('statement_timeout') as statement_timeout").fetchone()
    retain(db, apply=True)
    assert ledger_counts(db) == (0, 0, 0)
    after = db.execute("select current_setting('lock_timeout') as lock_timeout,"
                       "current_setting('statement_timeout') as statement_timeout").fetchone()
    assert after == before


def test_batch_lock_blocks_concurrent_membership_growth_during_count(db, disposable_database):
    from src.inventory_ingestion import ingest_vehicles
    from tests.test_inventory_postgres import vehicle
    source_id, _, _, batch, _ = seed_old(db)
    extra = []
    ingest_vehicles([vehicle()], _connection=db, _accepted_observations=extra)
    db.commit()
    attempted = []
    class Cursor:
        def __init__(self, cursor): self.inner = cursor
        def __enter__(self):
            self.inner.__enter__()
            return self
        def __exit__(self, *args): return self.inner.__exit__(*args)
        def __getattr__(self, name): return getattr(self.inner, name)
        def execute(self, statement, params=None):
            result = self.inner.execute(statement, params)
            if 'select m.observation_id' in statement and not attempted:
                attempted.append(True)
                # This is an actual second DB session performing an FK-backed
                # INSERT while retention holds existing batch FOR UPDATE locks.
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    with psycopg.connect(disposable_database) as other:
                        other.execute("set local lock_timeout='200ms'")
                        other.execute('insert into inventory_scan_memberships '
                            '(batch_id,source_id,listing_id,observation_id,evidence_kind) '
                            'values(%s,%s,%s,%s,%s)',
                            (batch['batch_id'], source_id, extra[0].listing_id,
                             extra[0].observation_id, 'positive'))
            return result
    class Connection:
        def transaction(self): return db.transaction()
        def cursor(self): return Cursor(db.cursor())
    result = retain(Connection())
    assert attempted == [True]
    assert result['eligible_memberships'] == 1
    assert ledger_counts(db) == (1, 1, 1)
