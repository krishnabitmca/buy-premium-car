from pathlib import Path
import json

import pytest

from src.dealer_inventory import parse_dealer_cards
from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter, execute_adapters


CASES = [
    ("bbt", "bbt_cards", "https://www.bigboytoyz.com/buy-used-mercedes-benz-cars", [49, 45]),
    ("autobest", "autobest_cards", "https://autobest.co.in/pre-owned-cars", [77.75, 47.75]),
    ("luxuryride", "luxuryride_cards", "https://luxuryrideofficial.com/", [69.75, 53.75]),
    ("9gear", "ninthgear_cards", "https://www.9thgear.co.in/luxury-used-cars-bangalore", [19.25, 61.75]),
]


def fixture(name):
    return Path(f"tests/fixtures/dealer_{name}.html").read_text()


@pytest.mark.parametrize("name,strategy,url,prices", CASES)
def test_real_dealer_cards_preserve_prices_photos_and_listing_links(name, strategy, url, prices):
    rows = parse_dealer_cards(fixture(name), name, url, strategy)
    assert [r["price_lakh"] for r in rows] == prices
    assert all(r["images"] and r["km"] and r["url"] != url for r in rows)
    assert all(r["condition_signal"] == "used" for r in rows)
    assert all(r["provenance"]["original_url"] == r["url"] for r in rows)


def test_bbt_unregistered_is_not_demo_and_registration_is_not_manufacture_year():
    rows = parse_dealer_cards(fixture("bbt"), "BBT", CASES[0][2], "bbt_cards")
    assert rows[0]["condition_signal"] == "used"
    assert rows[0]["registration_year"] is None
    assert rows[1]["registration_year"] == 2024
    assert rows[1]["mfg_year"] is None
    assert rows[1]["seller_state"] == "Odisha (OD)"


@pytest.mark.parametrize("name,strategy,url,prices", CASES)
def test_category_faq_and_duplicate_cards_cannot_create_extra_inventory(name, strategy, url, prices):
    html = fixture(name)
    rows = parse_dealer_cards(html + html + '<h1>Demo cars ₹20 Lakhs 2025 100 km</h1>', name, url, strategy)
    assert len(rows) == 2
    assert not parse_dealer_cards('<h1>Demo BMW X1 ₹20 Lakhs 2025 100 km</h1>', name, url, strategy)
    assert not parse_dealer_cards(html, name, url, strategy, "BMW X1")


def test_all_dealer_sources_aggregate_together_and_fail_independently(monkeypatch):
    registry = [{"name": name, "url": url, "parser_strategy": strategy, "adapter_status": "live"} for name, strategy, url, _ in CASES]
    pages = {url: fixture(name) for name, _, url, _ in CASES}
    monkeypatch.setattr("src.source_adapters.fetch_text", lambda url: pages[url])
    monkeypatch.setattr("src.source_adapters.adapter_execution_allowed", lambda _: True)
    monkeypatch.setattr("src.source_adapters.record_adapter_execution", lambda *a, **kw: None)
    rows, statuses = execute_adapters(AdapterRequest(condition="used"), registry)
    assert len(rows) == 8
    assert {r["source"] for r in rows} == {"bbt", "autobest", "luxuryride", "9gear"}
    assert all(s["listings_with_images"] == 2 for s in statuses)
    # Budget and exact model filters apply after source-specific extraction.
    rows, _ = execute_adapters(AdapterRequest(query="Mercedes-Benz E-Class", condition="used", budget_max=60), registry)
    assert len(rows) == 1 and rows[0]["source"] == "luxuryride"
    rows, _ = execute_adapters(AdapterRequest(condition="demo"), registry)
    assert not rows
    def partial(url):
        if url == CASES[0][2]:
            raise TimeoutError("source unavailable")
        return pages[url]
    monkeypatch.setattr("src.source_adapters.fetch_text", partial)
    rows, statuses = execute_adapters(AdapterRequest(condition="used"), registry)
    assert len(rows) == 6
    assert next(s for s in statuses if s["source"] == "bbt")["status"] == "unavailable"


def test_sold_reserved_and_zero_prices_are_excluded():
    html = fixture("9gear")
    assert not parse_dealer_cards(html.replace("New Arrival", "Recently Sold").replace("Less Driven", "Just Missed"), "9gear", CASES[3][2], "ninthgear_cards")
    assert not parse_dealer_cards(html.replace("19,25,000", "0").replace("61,75,000", "0"), "9gear", CASES[3][2], "ninthgear_cards")


def test_bbt_explicit_demo_flag_and_dynamic_model_family_are_correlated_to_visible_ids():
    state = [{"id": "134", "bid": "11", "modelname": "Mercedes C Class"},
             {"id": "2929", "brand": {"id": "11", "name": "Mercedes-Benz", "model": {"id": "134"}}, "price": 4900000, "isDemo": True, "inStock": True}]
    script = '<script>self.__next_f.push(' + json.dumps([1, '15:' + json.dumps(state)]) + ')</script>'
    rows = parse_dealer_cards(fixture("bbt") + script, "BBT", CASES[0][2], "bbt_cards", "Mercedes-Benz C-Class")
    assert len(rows) == 1
    assert rows[0]["model"] == "C Class" and rows[0]["condition_signal"] == "demo"
    assert rows[0]["provenance"]["condition_evidence"] == "product.isDemo=true"
    assert not parse_dealer_cards(script, "BBT", CASES[0][2], "bbt_cards")
    # Contradictory family metadata must not turn C200 into an E-Class.
    assert not parse_dealer_cards(fixture("bbt") + script.replace("Mercedes C Class", "Mercedes E Class"), "BBT", CASES[0][2], "bbt_cards", "Mercedes-Benz E-Class")
    assert not parse_dealer_cards(fixture("bbt") + script.replace('\\"inStock\\": true', '\\"inStock\\": false'), "BBT", CASES[0][2], "bbt_cards", "Mercedes-Benz C-Class")


def test_motozite_used_inventory_is_not_discarded_by_demo_default(monkeypatch):
    source = {"name": "Motozite", "url": "https://motozite.com/pre-owned-cars", "parser_strategy": "motozite_cards", "adapter_status": "live"}
    monkeypatch.setattr("src.source_adapters.fetch_text", lambda _: fixture("moto-used-merc"))
    monkeypatch.setattr("src.source_adapters.adapter_execution_allowed", lambda _: True)
    monkeypatch.setattr("src.source_adapters.record_adapter_execution", lambda *a, **kw: None)
    used = BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(query="Mercedes-Benz", condition="used"))
    assert len(used.listings) == 2
    assert all(r["condition_signal"] == "used" and r["images"] for r in used.listings)
    assert not BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(condition="demo")).listings
