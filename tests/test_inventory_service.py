from src import inventory_service as service


def test_cycle_schedules_then_consumes_persistent_work(monkeypatch):
    calls=[]
    def schedule(**kwargs):
        calls.append(('schedule',kwargs['limit']))
        return 4
    def consume(limit,**kwargs):
        if kwargs.get('demo_only'):
            calls.append(('demo',limit));return {'completed':0,'failed':0}
        calls.append(('consume',limit))
        return {'completed':2,'failed':1}
    monkeypatch.setattr(service,'schedule_refreshes',schedule)
    monkeypatch.setattr(service,'run_batch',consume)
    monkeypatch.setattr(service,'renew_listings',lambda limit:{'expired':0})
    assert service.run_cycle(7)=={'scheduled':4,'completed':2,'failed':1,'lifecycle':{'expired':0}}
    assert calls==[('schedule',7),('consume',6),('demo',1)]
