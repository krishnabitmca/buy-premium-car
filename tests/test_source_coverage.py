from src.source_intelligence import load_source_registry, plan_sources


def test_registered_sources_are_live_candidate_or_explicit_discovery_only():
    registry = load_source_registry(from_database=False)
    assert registry
    enabled = [s for s in registry if s.get("adapter_status") != "discovery_only"]
    assert enabled
    assert all(s.get("adapter_status") in {"live", "candidate"} for s in enabled)


def test_bmw_3_series_used_plan_has_broad_source_coverage():
    registry = load_source_registry(from_database=False)
    plan = plan_sources(
        brand="BMW",
        model="3 Series",
        condition="used",
        registry=registry,
        live_only=True,
    )
    names = {p["name"] for p in plan}
    expected = {
        "CarDekho Used",
        "CarWale Used",
        "Cars24 Luxury Used",
        "Spinny Luxury Used",
        "BMW Premium Selection",
        "CarTrade",
        "Droom",
        "OLX Cars",
        "Quikr Cars",
        "Big Boy Toyz",
        "AutoBest Emperio",
        "AutoHangar Used Cars",
        "9th Gear",
        "Luxury Ride",
        "Motozite",
    }
    missing = sorted(expected - names)
    assert not missing, f"BMW 3 Series source coverage missing: {missing}"
    assert len(names) >= len(expected)
