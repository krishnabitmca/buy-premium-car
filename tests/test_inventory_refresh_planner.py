from src.inventory_refresh_planner import _reliability
from src.inventory_freshness import refresh_priority


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
