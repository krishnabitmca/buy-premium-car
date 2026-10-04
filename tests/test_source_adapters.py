from src.source_adapters import AdapterRequest, AdapterResult, BuiltinMarketplaceAdapter, build_verified_adapters, execute_adapters, record_adapter_execution


def test_only_verified_live_sources_build_adapters():
    registry = [
        {"name": "Live", "adapter_status": "live", "url": "https://live.example"},
        {"name": "Candidate", "adapter_status": "candidate", "url": "https://candidate.example"},
        {"name": "Draft", "adapter_status": "candidate", "url": "https://draft.example"},
    ]

    adapters = build_verified_adapters(registry)

    assert [a.source_name for a in adapters] == ["Live"]


def test_adapter_failure_isolated_from_other_sources(monkeypatch):
    registry = [
        {"name": "Good", "adapter_status": "live", "url": "https://good.example"},
        {"name": "Bad", "adapter_status": "live", "url": "https://bad.example"},
    ]

    def fake_fetch(self, request):
        if self.source_name == "Bad":
            raise RuntimeError("source down")
        if self.source_name == "Good":
            return AdapterResult(
                source_name="Good",
                status="live",
                listings=[{
                    "brand": "BMW",
                    "model": "X5",
                    "price_lakh": 50,
                    "url": "https://good.example/car/1",
                    "source": "Good",
                    "live_verified": True,
                }],
            )

    monkeypatch.setattr(BuiltinMarketplaceAdapter, "fetch", fake_fetch)
    vehicles, statuses = execute_adapters(
        AdapterRequest(query="BMW X5", condition="used"),
        registry,
        max_workers=2,
    )

    assert len(vehicles) == 1
    assert vehicles[0]["source"] == "Good"
    assert {s["source"] for s in statuses} == {"Good", "Bad"}
    assert any(s["status"] == "unavailable" for s in statuses)


def test_adapter_failure_returns_source_specific_status(monkeypatch):
    registry = [
        {"name": "CarDekho Used", "adapter_status": "live", "url": "https://cardekho.example"}
    ]

    def fail_fetch(self, request):
        raise RuntimeError("timeout")

    monkeypatch.setattr(BuiltinMarketplaceAdapter, "fetch", fail_fetch)
    vehicles, statuses = execute_adapters(
        AdapterRequest(query="BMW X5", condition="used"),
        registry,
    )

    assert vehicles == []
    assert statuses[0]["source"] == "CarDekho Used"
    assert statuses[0]["status"] == "unavailable"


def test_builtin_adapter_uses_source_specific_target_url(monkeypatch):
    source = {
        "name": "CarDekho Used",
        "adapter_status": "live",
        "url": "https://www.cardekho.com/used-cars",
    }
    adapter = BuiltinMarketplaceAdapter(source)

    seen = {}

    monkeypatch.setattr(
        "src.source_adapters.fetch_text",
        lambda url: seen.setdefault("url", url) or "<html></html>",
    )
    monkeypatch.setattr(
        "src.source_adapters.parse_live_listings",
        lambda html, source_name, url: [],
    )
    monkeypatch.setattr(
        "src.source_adapters.parse_visible_listing_links",
        lambda html, source_name, url, query: [],
    )

    adapter.fetch(AdapterRequest(query="BMW X5", condition="used"))

    assert seen["url"] == "https://www.cardekho.com/used-bmw-x5+cars"


def test_open_circuit_is_not_executed(monkeypatch):
    source = {
        "name": "Broken",
        "adapter_status": "live",
        "url": "https://broken.example",
    }
    adapter = BuiltinMarketplaceAdapter(source)

    monkeypatch.setattr(
        "src.source_adapters.adapter_execution_allowed",
        lambda name: False,
    )
    result = adapter.fetch(AdapterRequest(query="BMW X5", condition="used"))

    assert result.status == "circuit_open"
    assert result.listings == []


def test_success_resets_adapter_health(monkeypatch):
    calls = {}

    class Cursor:
        def execute(self, sql, params=None):
            calls["sql"] = sql
            calls["params"] = params
        def __enter__(self): return self
        def __exit__(self, *args): pass

    class Conn:
        def cursor(self): return Cursor()
        def commit(self): calls["committed"] = True
        def __enter__(self): return self
        def __exit__(self, *args): pass

    monkeypatch.setattr("src.source_adapters.registry_db_enabled", lambda: True)
    monkeypatch.setattr("src.source_adapters.registry_connect", lambda: Conn())

    record_adapter_execution("Good", success=True, latency_ms=120)

    assert "circuit_state='closed'" in calls["sql"]
    assert calls["committed"] is True


def test_builtin_adapter_falls_back_to_visible_cards_for_unscoped_search(monkeypatch):
    source = {
        "name": "All Inventory Source",
        "adapter_status": "live",
        "url": "https://market.example/used-cars",
    }
    adapter = BuiltinMarketplaceAdapter(source)

    # Isolate this test to the fallback/parser contract; circuit-breaker state
    # belongs to a separate test and must not make this fixture environment-dependent.
    monkeypatch.setattr("src.source_adapters.adapter_execution_allowed", lambda name: True)
    monkeypatch.setattr("src.source_adapters.fetch_text", lambda url: "<html>listing cards</html>")
    monkeypatch.setattr("src.source_adapters.parse_live_listings", lambda html, source_name, url: [])
    monkeypatch.setattr(
        "src.source_adapters.parse_visible_listing_links",
        lambda html, source_name, url, query: [{
            "brand": "Maruti Suzuki",
            "model": "Swift",
            "price_lakh": 7.5,
            "url": "https://market.example/car/swift-1",
            "source": source_name,
            "condition_signal": "used",
            "live_verified": True,
            "data_consistent": True,
        }],
    )

    result = adapter.fetch(AdapterRequest(query="", condition="both"))

    assert result.status == "live"
    assert len(result.listings) == 1
    assert result.listings[0]["model"] == "Swift"
