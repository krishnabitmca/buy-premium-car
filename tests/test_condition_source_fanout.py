from src.source_intelligence import plan_sources


def test_demo_search_executes_only_demo_capable_sources():
    registry = [
        {"name":"OEM","adapter_status":"live","brands":["BMW"],"conditions":["used"],"segments":["premium"],"priority":90},
        {"name":"Marketplace","adapter_status":"live","brands":["all"],"conditions":["used"],"segments":["premium"],"priority":80},
        {"name":"Dealer","adapter_status":"live","brands":["BMW"],"conditions":["demo"],"segments":["premium"],"priority":70},
    ]
    names={x["name"] for x in plan_sources(brand="BMW",model="X1",condition="demo",registry=registry,live_only=True)}
    assert names == {"Dealer"}


def test_used_search_executes_only_used_capable_sources():
    registry = [
        {"name":"Mixed OEM","adapter_status":"live","brands":["BMW"],"conditions":["demo"],"segments":["premium"],"priority":90},
        {"name":"Mixed Dealer","adapter_status":"live","brands":["BMW"],"conditions":["used"],"segments":["premium"],"priority":80},
    ]
    names={x["name"] for x in plan_sources(brand="BMW",model="X1",condition="used",registry=registry,live_only=True)}
    assert names == {"Mixed Dealer"}


def test_demo_search_filters_out_used_and_unknown_rows_after_fanout(monkeypatch):
    from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter
    import src.source_adapters as adapters

    source = {"name": "Broad BMW Marketplace", "url": "https://example.com", "brands": ["BMW"], "conditions": ["used", "demo"]}
    monkeypatch.setattr(adapters, "fetch_text", lambda url: "<html></html>")
    monkeypatch.setattr(adapters, "parse_live_listings", lambda html, source_name, url: [
        {"brand":"BMW","model":"X1","name":"BMW X1 demonstrator","condition_signal":"demo"},
        {"brand":"BMW","model":"X1","name":"BMW X1 certified pre-owned","condition_signal":"used"},
        {"brand":"BMW","model":"X1","name":"BMW X1 xLine","condition_signal":"unknown"},
    ])
    result = BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(query="BMW X1", condition="demo"))
    assert len(result.listings) == 1
    assert result.listings[0]["condition_signal"] == "demo"
