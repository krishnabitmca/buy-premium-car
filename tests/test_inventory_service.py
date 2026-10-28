from src import inventory_service as service
import pytest


def test_cycle_schedules_then_consumes_persistent_work(monkeypatch):
    calls=[]
    def schedule(**kwargs):
        calls.append(('schedule',kwargs['limit']))
        return 4
    def consume(limit,**kwargs):
        kind=next(iter(kwargs),'general').removesuffix('_only')
        calls.append((kind,limit))
        return {'completed':limit,'failed':0}
    monkeypatch.setattr(service,'schedule_refreshes',schedule)
    monkeypatch.setattr(service,'run_batch',consume)
    monkeypatch.setattr(service,'renew_listings',lambda limit:{'expired':0})
    assert service.run_cycle(7)=={'scheduled':4,'completed':7,'failed':0,'lifecycle':{'expired':0}}
    assert calls==[('schedule',7),('general',1),('demo',1),('catalogues',3),('models',1),('continuations',1)]


def test_default_cycle_reserves_catalogues_before_model_fanout():
    plan=service.acquisition_plan(10)
    assert [(kind,budget) for kind,budget,_ in plan]==[('general',1),('demo',1),('catalogues',4),('models',2),('continuations',2)]
    assert sum(budget for _,budget,_ in service.acquisition_plan(1))==1
    assert sum(budget for _,budget,_ in service.acquisition_plan(200))==100


@pytest.mark.parametrize('stage',['schedule','acquire'])
def test_acquisition_failure_still_runs_listing_renewal(monkeypatch,stage):
    calls=[]
    monkeypatch.setattr(service,'schedule_refreshes',lambda **kw:0)
    def failed(*args,**kwargs):
        raise RuntimeError('acquisition failed')
    monkeypatch.setattr(service,'schedule_refreshes' if stage=='schedule' else 'run_batch',failed)
    monkeypatch.setattr(service,'renew_listings',lambda limit:calls.append(limit))
    with pytest.raises(RuntimeError,match='acquisition failed'):
        service.run_cycle(10)
    assert calls==[10]


def test_cycle_emits_bounded_bucket_progress(monkeypatch, caplog):
    """A long scheduled acquisition exposes the active work class without source URLs."""
    import logging

    monkeypatch.setattr(service, 'schedule_refreshes', lambda **kwargs: 2)
    monkeypatch.setattr(service, 'run_batch',
                        lambda budget, **kwargs: {'completed': budget, 'failed': 0})
    monkeypatch.setattr(service, 'renew_listings', lambda limit: {'expired': 0})
    with caplog.at_level(logging.INFO, logger=service.__name__):
        result = service.run_cycle(2)
    messages = [record.getMessage() for record in caplog.records
                if record.name == service.__name__]
    assert result['completed'] == 2
    assert 'Acquisition scheduling complete limit=2 scheduled=2' in messages
    assert 'Acquisition bucket start kind=general budget=1' in messages
    assert 'Acquisition bucket end kind=general completed=1 deferred=0 failed=0 superseded=0' in messages
    assert 'Acquisition bucket start kind=demo budget=1' in messages
    assert 'Acquisition bucket end kind=demo completed=1 deferred=0 failed=0 superseded=0' in messages
    assert all('https://' not in message for message in messages)


def test_cycle_logs_fallback_progress_without_changing_result(monkeypatch, caplog):
    import logging

    calls = []
    monkeypatch.setattr(service, 'schedule_refreshes', lambda **kwargs: 0)

    def consume(budget, **kwargs):
        calls.append((budget, kwargs))
        return {'completed': 0, 'failed': 0} if len(calls) < 3 else {'completed': budget, 'failed': 0}

    monkeypatch.setattr(service, 'run_batch', consume)
    monkeypatch.setattr(service, 'renew_listings', lambda limit: {'expired': 0})
    with caplog.at_level(logging.INFO, logger=service.__name__):
        result = service.run_cycle(2)
    messages = [record.getMessage() for record in caplog.records
                if record.name == service.__name__]
    assert result == {'scheduled': 0, 'completed': 2, 'failed': 0, 'lifecycle': {'expired': 0}}
    assert len(calls) == 3
    assert 'Acquisition fallback start budget=2' in messages
    assert 'Acquisition fallback end completed=2 deferred=0 failed=0 superseded=0' in messages
