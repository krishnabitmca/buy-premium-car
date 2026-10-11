from src.inventory_refresh_planner import _reliability
from src.inventory_freshness import refresh_priority
from src.inventory_refresh_planner import baseline_brand_demands


def test_baseline_uses_registry_taxonomy_without_picked_example_brands(monkeypatch):
    monkeypatch.setattr('src.inventory_refresh_planner.load_registry',lambda:[
        {'brands':['all','Audi','Toyota','Hyundai']},
        {'brands':['audi','Lexus','*','',None]},
    ])
    demands=baseline_brand_demands()
    assert [d['brand'] for d in demands]==['Audi','Hyundai','Lexus','Toyota']
    assert all(d['model']=='' and d['condition']=='both' and d['destination_state']=='' for d in demands)


def test_reliability_weights_known_health_states():
    assert _reliability("healthy") > _reliability("degraded")
    assert _reliability("degraded") > _reliability("unavailable")
    assert _reliability("unavailable") == _reliability("unhealthy")
    assert _reliability("blocked") < _reliability("unhealthy")


def test_demand_gap_and_staleness_increase_priority():
    fresh = refresh_priority(
        search_count=100, inventory_hit_count=90,
        freshness="fresh", source_reliability=1.0,
    )
    stale = refresh_priority(
        search_count=100, inventory_hit_count=90,
        freshness="stale", source_reliability=1.0,
    )
    high_gap = refresh_priority(
        search_count=100, inventory_hit_count=10,
        freshness="stale", source_reliability=1.0,
    )

    assert stale > fresh
    assert high_gap > stale
