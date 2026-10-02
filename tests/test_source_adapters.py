from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter, build_verified_adapters, execute_adapters


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
        return {
            "brand": "BMW",
            "model": "X5",
            "price_lakh": 50,
            "url": "https://good.example/car/1",
            "source": "Good",
            "live_verified": True,
        }

    # Exercise the executor's defensive isolation path by replacing the
    # adapter fetch implementation. The good source must still return data.
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
    assert statuses[0]["source"] == "unknown"
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
