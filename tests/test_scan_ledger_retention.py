from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.scan_ledger_retention import retain_scan_ledger, _reference


class Connection:
    def __init__(self,responses):
        self.responses=iter(responses)
        self.calls=[]
        self.rolled_back=False
    @contextmanager
    def transaction(self):
        try:yield
        except Exception:
            self.rolled_back=True
            raise
    def cursor(self):return self
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params):self.calls.append((sql,params))
    def fetchone(self):return next(self.responses)
    def fetchall(self):return next(self.responses)


def fixture(*,queue=None,current=None,batches=None,members=None,deleted=True):
    cutoff=datetime.now(timezone.utc)-timedelta(days=30)
    old=cutoff-timedelta(days=1)
    generation=uuid4()
    responses=[{'cutoff':cutoff,'prior_lock':'0','prior_statement':'0'},[{'generation_id':generation,'refresh_id':1}],
        queue or {'status':'completed','metadata':{}},
        current or {'captured_at':old,'last_batch_at':old},
        batches if batches is not None else [{'completed_at':old,'claim_started_at':old}],
        members if members is not None else [{'observation_id':1}],
        {'generation_id':generation} if deleted else None]
    return Connection(responses),generation


def test_default_dryrun_counts_without_deleting():
    conn,_=fixture()
    report=retain_scan_ledger(_connection=conn)
    assert report['eligible_generations']==report['eligible_batches']==report['eligible_memberships']==1
    assert report['deleted_generations']==0
    assert not report['locked_counts_available']
    assert not any(sql.startswith('delete') for sql,_ in conn.calls)


def test_apply_deletes_only_generation_after_queue_then_generation_lock():
    conn,_=fixture()
    report=retain_scan_ledger(apply=True,_connection=conn)
    assert report['deleted_generations']==report['deleted_batches']==report['deleted_memberships']==1
    assert 'inventory_refresh_queue' in conn.calls[2][0]
    assert 'for update skip locked' in conn.calls[2][0]
    assert 'inventory_scan_generations' in conn.calls[3][0]
    assert [sql.split()[2] for sql,_ in conn.calls if sql.startswith('delete')] == ['inventory_scan_generations']


@pytest.mark.parametrize('status',['queued','running'])
def test_active_queue_is_protected(status):
    conn,_=fixture(queue={'status':status,'metadata':{}})
    report=retain_scan_ledger(apply=True,_connection=conn)
    assert report['skipped']['active']==1 and report['deleted_generations']==0
    assert len(conn.calls)==4


@pytest.mark.parametrize('metadata',[None,[],{'continuation':None},{'continuation':{}},
    {'continuation':{'scan_generation':{'generation_id':'invalid'}}}])
def test_malformed_checkpoint_protects_queue(metadata):
    conn,_=fixture(queue={'status':'failed','metadata':metadata})
    assert retain_scan_ledger(apply=True,_connection=conn)['skipped']['malformed']==1


def test_reference_protected_in_failed_or_cancelled_queue():
    for status in ('failed','cancelled','completed'):
        conn,generation=fixture()
        conn.responses=iter([{'cutoff':datetime.now(timezone.utc),'prior_lock':'0','prior_statement':'0'},
            [{'generation_id':generation,'refresh_id':1}],
            {'status':status,'metadata':{'continuation':{'scan_generation':{'generation_id':str(generation)}}}}])
        assert retain_scan_ledger(apply=True,_connection=conn)['skipped']['referenced']==1


def test_incomplete_and_recent_batches_are_protected():
    now=datetime.now(timezone.utc)
    for batch,reason in (({'completed_at':None,'claim_started_at':now},'incomplete'),
                         ({'completed_at':now,'claim_started_at':now},'recent')):
        conn,_=fixture(batches=[batch])
        assert retain_scan_ledger(apply=True,_connection=conn)['skipped'][reason]==1


def test_oversized_generation_is_not_partially_pruned():
    conn,_=fixture(members=[{'observation_id':1},{'observation_id':2}])
    report=retain_scan_ledger(apply=True,membership_limit=1,_connection=conn)
    assert report['skipped']['oversized']==1 and report['deleted_memberships']==0


def test_failed_delete_rolls_back_entire_operation():
    conn,_=fixture(deleted=False)
    with pytest.raises(RuntimeError):retain_scan_ledger(apply=True,_connection=conn)
    assert conn.rolled_back


@pytest.mark.parametrize('arguments',[{'apply':'true'},{'retention_days':29},{'retention_days':True},
    {'generation_limit':11},{'batch_limit':101},{'membership_limit':1001},{'candidate_limit':201}])
def test_invalid_config_rejected_before_connect(arguments):
    with pytest.raises(ValueError):retain_scan_ledger(**arguments,_connection=Connection([]))


def test_unavailable_queue_is_not_reported_as_total_locked_rows():
    conn,generation=fixture()
    conn.responses=iter([{'cutoff':datetime.now(timezone.utc),'prior_lock':'0','prior_statement':'0'},
        [{'generation_id':generation,'refresh_id':1}],None])
    report=retain_scan_ledger(_connection=conn)
    assert report['skipped']['unavailable']==1 and report['locked_counts_available'] is False
