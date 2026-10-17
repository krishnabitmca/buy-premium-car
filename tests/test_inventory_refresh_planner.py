from src.inventory_refresh_planner import _reliability
from src.inventory_freshness import refresh_priority
from src.inventory_refresh_planner import baseline_brand_demands


def test_baseline_uses_registry_taxonomy_without_picked_example_brands(monkeypatch):
    monkeypatch.setattr('src.inventory_refresh_planner.CAR_MAKES',['Mahindra','Skoda','Honda'])
    monkeypatch.setattr('src.inventory_refresh_planner.load_registry',lambda:[
        {'brands':['all','Audi','Toyota','Hyundai']},
        {'brands':['audi','Lexus','*','',None]},
    ])
    demands=baseline_brand_demands()
    assert [d['brand'] for d in demands]==['Audi','Honda','Hyundai','Lexus','Mahindra','Skoda','Toyota']
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


def test_brand_identity_is_independent_of_source_capability_completeness(monkeypatch):
    from src import live_marketplaces as lm
    monkeypatch.setattr(lm,'_registry_brand_records',lambda:[])
    monkeypatch.setattr(lm,'_configured_brand_records',lambda:[])
    for brand in ('Mahindra','Skoda','Honda','Hyundai'):
        assert lm._query_parts(brand)==(brand,None)
        assert lm._query_parts(brand+' City')[0]==brand


def test_missing_registry_make_can_fetch_real_configured_catalog_models(monkeypatch):
    from src import live_marketplaces as lm
    monkeypatch.setattr(lm,'live_brands',lambda:[{'name':'BMW','url':'https://catalog.example/bmw-cars'}])
    monkeypatch.setattr(lm,'load_source_registry',lambda:[{'catalog_brand_url_template':'https://catalog.example/{brand_slug}-cars'}])
    seen=[]
    monkeypatch.setattr(lm,'fetch_text',lambda url:seen.append(url) or '<a href="/mahindra/thar">Mahindra Thar</a>')
    assert [m['name'] for m in lm.live_models('Mahindra')]==['Thar']
    assert seen==['https://catalog.example/mahindra-cars']
