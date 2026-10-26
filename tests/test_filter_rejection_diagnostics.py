"""Source filter diagnostics are aggregate evidence, not inventory absence proof."""
from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter
from src.extraction_telemetry import summarize_committed_refresh


def test_filter_rejection_reasons_are_counted_without_changing_results(monkeypatch):
    source = {"name": "Fixture Source", "adapter_status": "live", "url": "https://example.invalid/catalog"}
    rows = [
        {"brand": "Audi", "model": "A4", "url": "https://example.invalid/1", "condition_signal": "demo", "price_lakh": 40},
        {"brand": "BMW", "model": "X1", "url": "https://example.invalid/2", "condition_signal": "used", "price_lakh": 40},
        {"brand": "BMW", "model": "X1", "url": "https://example.invalid/3", "condition_signal": "demo", "price_lakh": None},
        {"brand": "BMW", "model": "X1", "url": "https://example.invalid/4", "condition_signal": "demo", "price_lakh": 20},
        {"brand": "BMW", "model": "X1", "url": "https://example.invalid/5", "condition_signal": "demo", "price_lakh": 60},
        {"brand": "BMW", "model": "X1", "url": "https://example.invalid/6", "condition_signal": "demo", "price_lakh": 40},
    ]
    monkeypatch.setattr("src.source_adapters.fetch_text", lambda url: "<html></html>")
    monkeypatch.setattr("src.source_adapters.parse_live_listings", lambda *args: rows + [dict(rows[-1])])
    monkeypatch.setattr("src.source_adapters.parse_visible_listing_links", lambda *args: [])
    monkeypatch.setattr("src.source_adapters.live_marketplaces._targeted_source_urls", lambda *args, **kwargs: {})
    monkeypatch.setattr("src.source_adapters.live_marketplaces._identity_matches_query", lambda row, query: row.get('brand') == 'BMW')
    result = BuiltinMarketplaceAdapter(source).fetch(
        AdapterRequest(query="BMW", condition="demo", budget_min=30, budget_max=50))
    assert result.status == "live", result.error
    assert len(result.listings) == 1
    assert result.listings[0]["url"].endswith("/6")
    quality = result.scan_evidence["scraper_quality"]
    assert quality["deduplicated_within_source_count"] == 1
    assert quality["filter_rejection_counts"]["identity"] == 1
    assert quality["filter_rejection_counts"]["demo_evidence"] == 1
    assert quality["filter_rejection_counts"]["below_min_or_missing_price"] == 2
    assert quality["filter_rejection_counts"]["above_max_or_missing_price"] == 1
    telemetry = summarize_committed_refresh(result.scan_evidence,
        pages_fetched=result.pages_fetched, listings_extracted=len(result.listings), listings_ingested=1)
    assert telemetry["filter_rejection_counts"] == {k: v for k, v in quality["filter_rejection_counts"].items()}
    assert telemetry["deduplicated_within_source_count"] == 1
    assert telemetry["absence_reconciliation_permitted"] is False


def test_telemetry_drops_untrusted_labels_and_malformed_counters():
    evidence = {"scraper_quality": {
        "filter_rejection_counts": {"identity": 3, "demo_evidence": True,
                                    "secret_token": 900, "above_max_or_missing_price": -1},
        "deduplicated_within_source_count": "invalid",
    }}
    telemetry = summarize_committed_refresh(evidence, pages_fetched=1,
                                             listings_extracted=0, listings_ingested=0)
    assert telemetry["filter_rejection_counts"] == {"identity": 3}
    assert telemetry["deduplicated_within_source_count"] == 0
    assert "secret_token" not in str(telemetry)
    assert telemetry["absence_reconciliation_permitted"] is False
