import pytest

from src.live_marketplaces import parse_generic_detail_page
from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter


@pytest.mark.parametrize("url", [
    "https://motozite.com/demo/bmw/x1/all",
    "https://market.example/search/bmw-x1",
])
def test_category_heading_is_not_a_vehicle(url):
    html = '<title>Demo BMW X1 for Sale in India – Motozite</title><h1>Discover Demo Car by</h1><meta property="og:image" content="/NewCar.jpg">'
    assert parse_generic_detail_page(html, "Motozite Demo", url, "BMW X1") == []


def test_category_with_price_filters_is_not_a_vehicle():
    html = '<h1>2025 BMW X1 demo</h1><p>₹42 Lakh Manufacturing Year 2025 Mileage 3,200 KM</p>'
    assert parse_generic_detail_page(html, "Test", "https://example.com/demo/bmw/x1/all", "BMW X1") == []


def test_real_individual_detail_retains_price_specs_photo_and_provenance():
    html = '''<h1>2025 BMW X1 sDrive20i Demo</h1>
    <meta property="og:image" content="/photos/vehicle-123.jpg">
    <script>₹1 Lakh Manufacturing Year 2001 Mileage 999 KM</script>
    <p>₹42.50 Lakh Manufacturing Year 2025 Current Mileage 3,200 KM</p>'''
    url = "https://market.example/vehicle/123"
    rows = parse_generic_detail_page(html, "Dealer", url, "BMW X1")
    assert len(rows) == 1
    row = rows[0]
    assert row["price_lakh"] == 42.5
    assert row["mfg_year"] == 2025
    assert row["km"] == 3200
    assert row["condition_signal"] == "demo"
    assert row["images"] == ["https://market.example/photos/vehicle-123.jpg"]
    assert row["provenance"]["original_url"] == url


def test_detail_without_individual_specs_is_not_verified():
    html = '<h1>BMW X1 Demo</h1><p>₹42 Lakh</p>'
    assert parse_generic_detail_page(html, "Test", "https://example.com/car/123", "BMW X1") == []


def test_request_identity_cannot_be_assigned_to_different_vehicle():
    html = '<h1>2025 BMW X5 Demo</h1><p>₹70 Lakh Manufacturing Year 2025 Mileage 3,200 KM</p>'
    assert parse_generic_detail_page(html, "Test", "https://example.com/car/123", "BMW X1") == []


def test_adapter_reads_database_parser_strategy_and_preserves_real_listing(monkeypatch):
    html = '''<div id="car_item_123" class="carlistblk">
    <a href="/car/123"><img src="/123.jpg" /></a></div>
    <a data-title="BMW X1 Demo" data-price="4200000" data-mfgyear="2025"
       data-listingid="123" data-make="BMW" data-model="X1" data-city="Delhi"
       data-condition="demo">3,200 km Petrol</a>'''
    source = {"name": "BMW Premium Selection", "adapter_status": "live",
              "url": "https://example.com/buy-used-cars",
              "metadata": {"parser_strategy": "bmw_cards"}}
    monkeypatch.setattr("src.source_adapters.adapter_execution_allowed", lambda _: True)
    monkeypatch.setattr("src.source_adapters.fetch_text", lambda _: html)
    monkeypatch.setattr("src.source_adapters.record_adapter_execution", lambda *a, **kw: None)
    result = BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(query="BMW X1", condition="demo"))
    assert len(result.listings) == 1
    assert result.listings[0]["url"] == "https://example.com/car/123"
    assert result.listings[0]["price_lakh"] == 42


def test_adapter_does_not_promote_empty_motozite_category(monkeypatch):
    source = {"name": "Motozite Demo", "adapter_status": "live",
              "url": "https://motozite.com/demo/bmw/x1/all"}
    monkeypatch.setattr("src.source_adapters.adapter_execution_allowed", lambda _: True)
    monkeypatch.setattr("src.source_adapters.fetch_text", lambda _: '<title>Demo BMW X1 for Sale in India – Motozite</title>')
    monkeypatch.setattr("src.source_adapters.record_adapter_execution", lambda *a, **kw: None)
    result = BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(query="BMW X1", condition="demo"))
    assert result.status == "live"
    assert result.listings == []
