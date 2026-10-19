"""Operator verifier must reject inconclusive or unrelated work."""
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from scripts import verify_scan_ledger as verifier


@pytest.fixture
def operator(monkeypatch):
    source_id = uuid4()
    job = dict(source_id=source_id, refresh_id=17, attempt_count=3,
               started_at=datetime.now(timezone.utc))
    batch = dict(batch_id=uuid4(), accepted_count=2, memberships=2,
                 positive_observations=1, completeness_verified=False,
                 absence_reconciliation_permitted=False)
    queries = []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def commit(self): pass
        def execute(self, statement, params=None):
            queries.append((statement, params))
            if 'select s.source_id' in statement:
                return Mock(fetchone=lambda: {'source_id': source_id})
            if 'clock_timestamp' in statement:
                return Mock(fetchone=lambda: {'stamp': job['started_at'], 'role': 'worker_fixture'})
            if 'has_table_privilege' in statement:
                return Mock(fetchone=lambda: {'allowed': True})
            # Emulate exact-claim SQL retrieval, rather than returning arbitrary
            # records regardless of its predicate.
            assert 'b.refresh_id=%s' in statement
            assert 'b.attempt_count=%s' in statement
            assert 'b.claim_started_at=%s' in statement
            assert 'b.completed_at is not null' in statement
            assert params == (source_id, job['refresh_id'], job['attempt_count'], job['started_at'])
            return Mock(fetchall=lambda: state['batches'])
    state = dict(job=job, batches=[batch], batch=batch, queries=queries)
    monkeypatch.setenv('CARSCANNER_SCAN_LEDGER_ENABLED', 'true')
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE', '20')
    monkeypatch.setattr(verifier, 'require_database', lambda: None)
    monkeypatch.setattr(verifier, '_connect', Connection)
    state['claim'] = Mock(return_value=[job])
    state['process'] = Mock(return_value={'observations': 2})
    monkeypatch.setattr(verifier, 'claim_jobs', state['claim'])
    monkeypatch.setattr(verifier, 'process_job', state['process'])
    return state


def test_verify_requires_claimable_work(operator):
    operator['claim'].return_value = []
    with pytest.raises(RuntimeError, match='No claimable'):
        verifier.verify('Fixture Dealer')
    operator['process'].assert_not_called()


@pytest.mark.parametrize('outcome', ['deferred', 'superseded'])
def test_verify_rejects_uncommitted_worker_outcomes(operator, outcome):
    operator['process'].return_value = {outcome: 1}
    with pytest.raises(RuntimeError, match='deferred or superseded'):
        verifier.verify('Fixture Dealer')
    assert not any('from inventory_scan_batches' in sql for sql, _ in operator['queries'])


def test_verify_rejects_negative_only_membership(operator):
    operator['batch']['positive_observations'] = 0
    with pytest.raises(RuntimeError, match='positive membership unverified'):
        verifier.verify('Fixture Dealer')


def test_unrelated_committed_batch_cannot_satisfy_this_claim(operator):
    # A different claim's batch is absent from the exact-claim query result.
    operator['batches'] = []
    with pytest.raises(RuntimeError, match='Expected one committed ledger batch'):
        verifier.verify('Fixture Dealer')


def test_verify_returns_exact_claim_positive_evidence_and_bounds(operator, monkeypatch):
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE', '50')
    result = verifier.verify('Fixture Dealer', 'Honda')
    operator['claim'].assert_called_once_with(1, source_names=['Fixture Dealer'], brands=['Honda'])
    operator['process'].assert_called_once_with(operator['job'])
    assert result['worker_role'] == 'worker_fixture'
    assert result['positive_observations'] == 1
    assert result['accepted_observations'] == result['memberships'] == 2
    assert result['batch_id'] == str(operator['batch']['batch_id'])
    assert result['maximum_jobs'] == result['page_budget'] == 1
    import os
    assert os.environ['CARSCANNER_MAX_PAGES_PER_SOURCE'] == '1'


@pytest.mark.parametrize('mutation', [{'memberships': 1}, {'completeness_verified': True},
                                      {'absence_reconciliation_permitted': True}])
def test_verify_rejects_membership_or_authority_inconsistency(operator, mutation):
    operator['batch'].update(mutation)
    with pytest.raises(RuntimeError, match='invariant failed'):
        verifier.verify('Fixture Dealer')
