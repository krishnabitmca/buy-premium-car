from contextlib import nullcontext
from types import SimpleNamespace
import pytest
from src import inventory_lifecycle as lifecycle


@pytest.mark.parametrize('demo_ready',[False,True])
def test_idle_condition_slots_are_borrowed_without_losing_demo_reservation(monkeypatch,demo_ready):
    monkeypatch.setattr(lifecycle,'require_database',lambda:None)
    connection=SimpleNamespace(execute=lambda *args:SimpleNamespace(fetchone=lambda:{'last_start':None}),commit=lambda:None)
    monkeypatch.setattr(lifecycle,'_connect',lambda:nullcontext(connection))
    monkeypatch.setattr(lifecycle,'maintain',lambda:{'expired':0})
    requests=[];executed=[]
    def claim(condition):
        requests.append(condition)
        return {'condition':condition} if condition=='used' or demo_ready else None
    monkeypatch.setattr(lifecycle,'claim',claim)
    monkeypatch.setattr(lifecycle,'revalidate',lambda job:executed.append(job['condition']) or 'available')
    assert lifecycle.run_cycle(10)['available']==10
    assert executed==(['demo','used']*5 if demo_ready else ['used']*10)
