"""Private ledger validation; real FK/rollback coverage lives in integration."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.inventory_ingestion import AcceptedObservation
from src.scan_contract import generation, outcome, scan_scope
from src.scan_ledger import prepare_batch, finish_batch
from src.source_adapters import AdapterRequest


class Connection:
    def __init__(self, responses=()):
        self.responses = iter(responses)
        self.calls = []
    def cursor(self): return self
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self,sql,params): self.calls.append((sql,params))
    def fetchone(self): return next(self.responses)


def sample(pending=False):
    source_id = uuid4()
    scope, fingerprint = scan_scope({'source_id':source_id}, AdapterRequest(continuation={}),
                                    ['https://fixture.invalid/'])
    evidence = dict(scope=scope,pages_this_batch=2,
                    **outcome(generation({},fingerprint),pending=pending,background=True))
    job = dict(refresh_id=4,source_id=source_id,attempt_count=2,
               started_at=datetime.now(timezone.utc))
    row = dict(generation_id=UUID(evidence['generation_id']),
               source_id=source_id,refresh_id=4,scope_fingerprint=fingerprint,
               started_at=datetime.fromisoformat(evidence['started_at']),contract_version=1,
               legacy_partial_history=False)
    return job,evidence,row


def prepared(pending=False):
    job,evidence,row = sample(pending)
    conn = Connection([row, {'batch_id':uuid4()}])
    return prepare_batch(job,job['source_id'],evidence,conn), evidence, conn


def test_prepare_uses_stable_claim_identity_and_preserves_caller_transaction():
    job,evidence,row = sample()
    first = prepare_batch(job,job['source_id'],evidence,Connection([row, {'batch_id':uuid4()}]))
    second = prepare_batch(job,job['source_id'],evidence,Connection([row, {'batch_id':uuid4()}]))
    assert first['batch_id'] == second['batch_id']
    assert not first['already_committed']
    existing = dict(batch_id=first['batch_id'],generation_id=first['generation_id'],
        source_id=job['source_id'],refresh_id=4,attempt_count=2,claim_started_at=job['started_at'],
        completed_at=datetime.now(timezone.utc))
    duplicate = prepare_batch(job,job['source_id'],evidence,Connection([row,None,existing]))
    assert duplicate['already_committed']
    existing['completed_at'] = None
    with pytest.raises(ValueError,match='incomplete'):
        prepare_batch(job,job['source_id'],evidence,Connection([row,None,existing]))


@pytest.mark.parametrize('key,value', [
    ('generation_id','not-a-uuid'),('scope_fingerprint','bad'),('started_at','2026-10-19'),
    ('contract_version',True),('contract_version',999),('background_scan',False),
    ('completeness_verified',True),('absence_reconciliation_permitted',True),
    ('pages_this_batch',True),('pages_this_batch',-1),('terminal_reason','complete'),
    ('resumed_legacy_checkpoint',None),('execution_state','failed')])
def test_malformed_evidence_rejected_before_sql(key,value):
    job,evidence,_ = sample()
    evidence[key]=value
    conn=Connection()
    with pytest.raises(ValueError):prepare_batch(job,job['source_id'],evidence,conn)
    assert conn.calls == []


def test_generation_conflicts_rejected_and_scope_hash_checked():
    job,evidence,row = sample()
    with pytest.raises(ValueError,match='immutable'):
        prepare_batch(job,job['source_id'],evidence,Connection([{**row,'refresh_id':999}]))
    changed = deepcopy(evidence)
    changed['scope']['query']='different scope'
    conn=Connection()
    with pytest.raises(ValueError,match='fingerprint'):
        prepare_batch(job,job['source_id'],changed,conn)
    assert not conn.calls


def test_finish_keeps_repeated_listing_observations_and_does_not_regress_state():
    batch,evidence,_ = prepared()
    listing=uuid4()
    records=[AcceptedObservation(batch['source_id'],listing,1,'positive'),
             AcceptedObservation(batch['source_id'],listing,2,'explicit_negative')]
    conn=Connection([{'batch_id':batch['batch_id']}])
    finish_batch(batch,records,evidence,None,conn)
    assert len([q for q,p in conn.calls if q.startswith('insert into inventory_scan_memberships')])==2
    assert 'state=case when state=' in conn.calls[-1][0]
    assert conn.calls[-2][1][:2] == (2,2)


def test_finish_validates_pending_checkpoint_and_source_before_writes():
    batch,evidence,_ = prepared(True)
    conn=Connection()
    with pytest.raises(ValueError,match='checkpoint'):
        finish_batch(batch,[],evidence,None,conn)
    checkpoint = {key:evidence[key] for key in ('generation_id','scope_fingerprint',
        'contract_version','started_at','resumed_legacy_checkpoint')}
    record=AcceptedObservation(uuid4(),uuid4(),3,'positive')
    with pytest.raises(ValueError,match='source'):
        finish_batch(batch,[record],evidence,{'scan_generation':checkpoint},conn)
    assert not conn.calls
    finish_batch(batch,[],evidence,{'scan_generation':checkpoint},Connection([{'batch_id':batch['batch_id']}]))


def test_finish_rejects_duplicate_observation_and_committed_batch():
    batch,evidence,_ = prepared()
    record=AcceptedObservation(batch['source_id'],uuid4(),5,'positive')
    conn=Connection()
    with pytest.raises(ValueError,match='Duplicate'):
        finish_batch(batch,[record,record],evidence,None,conn)
    assert not conn.calls
    with pytest.raises(ValueError,match='committed'):
        finish_batch({**batch,'already_committed':True},[],evidence,None,conn)
