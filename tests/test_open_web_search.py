from src.query_discovery import discover_for_intent, merge_source_universe


def test_registry_is_cache_not_search_universe(monkeypatch):
    import src.query_discovery as qd

    class Candidate:
        url="https://new-bmw-dealer.example/inventory/x1"
        domain="new-bmw-dealer.example"
        source_type="dealer_network"
        segment="luxury"
        query='"BMW X1" demo cars India'
        candidate_confidence=.91

    captured={}
    def fake_discover(settings, known_domains, demand=None, **kwargs):
        captured["demand"]=demand
        return [Candidate()]

    monkeypatch.setattr(qd, "discover", fake_discover)
    monkeypatch.setattr(qd, "fetch_text", lambda url: "<html/>")
    monkeypatch.setattr(qd, "parse_live_listings", lambda *args: [
        {"brand":"BMW","model":"X1","listing_name":"BMW X1 demonstrator","condition_signal":"demo"}
    ])

    registry=[{"name":"Motozite","url":"https://motozite.com","adapter_status":"live"}]
    found=discover_for_intent(
        brand="BMW",model="X1",condition="demo",known_registry=registry
    )

    assert captured["demand"][0]["brand"]=="BMW"
    assert captured["demand"][0]["model"]=="X1"
    assert found[0]["url"]=="https://new-bmw-dealer.example/inventory/x1"
    assert found[0]["conditions"]==["used","demo"]


def test_same_open_web_expansion_applies_to_any_brand_model(monkeypatch):
    import src.query_discovery as qd

    class Candidate:
        url="https://dealer.example/audi/q5"
        domain="dealer.example"
        source_type="dealer_network"
        segment="luxury"
        query='"Audi Q5" used cars India'
        candidate_confidence=.9

    monkeypatch.setattr(qd, "discover", lambda settings, known_domains, demand=None, **kwargs: [Candidate()])
    monkeypatch.setattr(qd, "fetch_text", lambda url: "<html/>")
    monkeypatch.setattr(qd, "parse_live_listings", lambda *args: [
        {"brand":"Audi","model":"Q5","listing_name":"Audi Q5 pre-owned","condition_signal":"used"}
    ])

    found=discover_for_intent(
        brand="Audi",model="Q5",condition="used",known_registry=[]
    )
    assert len(found)==1
    assert found[0]["query_strategy"]=="open_web_intent"


def test_merge_keeps_registry_and_adds_new_endpoints_even_on_known_domain():
    registry=[{"name":"Known","url":"https://known.example/cars"}]
    discovered=[
        {"name":"New endpoint","url":"https://known.example/bmw/x1-demo"},
        {"name":"New domain","url":"https://new.example/cars"},
    ]
    merged=merge_source_universe(registry,discovered)
    assert [x["name"] for x in merged]==["Known","New endpoint","New domain"]


def test_condition_is_listing_evidence_not_source_name():
    from api.search import _vehicle_condition
    assert _vehicle_condition({"source":"BMW Demo Cars","condition_signal":"unknown"})=="unknown"
    assert _vehicle_condition({"source":"Used Marketplace","condition_signal":"demo"})=="demo"


def test_intent_discovery_requests_known_domain_endpoints(monkeypatch):
    import src.query_discovery as qd

    captured={}
    def fake_discover(settings, known_domains, demand=None, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(qd, "discover", fake_discover)
    discover_for_intent(
        brand="BMW", model="X1", condition="demo",
        known_registry=[{"url":"https://dealer.example/cars"}],
    )
    assert captured["include_known_domain_urls"] is True
    assert captured["max_queries"] == 9


def test_demo_discovery_rejects_identity_only_without_demo_evidence(monkeypatch):
    import src.query_discovery as qd
    class Candidate:
        url="https://cars.example/bmw/x1"
        domain="cars.example"
        source_type="marketplace"
        segment="luxury"
        query='"BMW X1" demo cars India'
        candidate_confidence=.9
    monkeypatch.setattr(qd,"discover",lambda *args,**kwargs:[Candidate()])
    monkeypatch.setattr(qd,"fetch_text",lambda url:"<html/>")
    monkeypatch.setattr(qd,"parse_live_listings",lambda *args:[
        {"brand":"BMW","model":"X1","listing_name":"BMW X1 new car","condition_signal":"unknown"}
    ])
    assert discover_for_intent(brand="BMW",model="X1",condition="demo",known_registry=[])==[]
