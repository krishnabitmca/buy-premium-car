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
    assert calls==[('schedule',7),('general',1),('demo',1),('catalogues',1),('models',2),('continuations',2)]


def test_default_cycle_reserves_catalogues_before_model_fanout():
    plan=service.acquisition_plan(10)
    assert [(kind,budget) for kind,budget,_ in plan]==[('general',1),('demo',1),('catalogues',2),('models',3),('continuations',3)]
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
