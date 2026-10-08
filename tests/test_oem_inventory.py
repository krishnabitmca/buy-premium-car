import json
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from src.oem_inventory import parse_mercedes_cards, fetch_mercedes_inventory
from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter

URL = "https://www.mercedes-benzusedcar.in/buy-used-cars?ctype=demonstrator"
HTML = Path("tests/fixtures/mercedes_demo_cards.html").read_text()


def test_actual_oem_cards_have_individual_evidence_and_photos():
    rows = parse_mercedes_cards(HTML, "Mercedes-Benz Used Cars", URL, "Mercedes-Benz E-Class")
    assert len(rows) == 2
    assert [r["price_lakh"] for r in rows] == [67.5, 73]
    assert [r["location"] for r in rows] == ["New Delhi", "Bangalore"]
    assert [r["km"] for r in rows] == [15775, 1980]
    assert all(r["condition_signal"] == "demo" and r["images"] for r in rows)
    assert all(r["url"].endswith(".html") for r in rows)
    assert all(r["model"] == "E-Class" for r in rows)


def test_listing_condition_is_not_inherited_from_demo_route():
    html = HTML.replace("Demonstrator", "Pre-Owned")
    rows = parse_mercedes_cards(html, "OEM", URL, "Mercedes-Benz E-Class")
    assert len(rows) == 2
    assert all(r["condition_signal"] == "used" for r in rows)
    assert not parse_mercedes_cards(HTML, "OEM", URL, "Mercedes-Benz C-Class")
    assert not parse_mercedes_cards('<h1>Mercedes-Benz E-Class Demonstrator</h1>', "OEM", URL, "Mercedes-Benz E-Class")


def test_public_inventory_transport_uses_session_tokens_and_model_filter(monkeypatch):
    seen = []
    class Response:
        def __init__(self, text): self.text = text
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return self.text.encode()
    class Opener:
        def open(self, request, timeout):
            seen.append(request)
            return Response(json.dumps({"details": {"security_token1": "public1", "security_token2": "public2", "security_token2_rand": "public3"}}) if request.data is None else HTML)
    monkeypatch.setattr("src.oem_inventory.urllib.request.build_opener", lambda *a: Opener())
    rows = fetch_mercedes_inventory(URL, "Mercedes-Benz E-Class", "demo", "OEM")
    assert len(rows) == 2
    fields = parse_qs(seen[1].data.decode())
    assert fields["action"] == ["get_inventory"]
    assert fields["ctype"] == ["demonstrator"]
    assert fields["model"] == ["E Class"]
    assert fields["security_token1"] == ["public1"]
    assert "security_token" not in json.dumps(rows)


def test_oem_host_is_restricted():
    with pytest.raises(ValueError):
        fetch_mercedes_inventory("https://unrelated.example/cars", "", "demo", "OEM")


def test_adapter_filters_oem_used_cars_out_of_demo_results(monkeypatch):
    source = {"name": "Mercedes-Benz Used Cars", "adapter_status": "live", "url": URL, "parser_strategy": "mercedes_inventory"}
    monkeypatch.setattr("src.source_adapters.adapter_execution_allowed", lambda _: True)
    monkeypatch.setattr("src.source_adapters.record_adapter_execution", lambda *a, **kw: None)
    rows = parse_mercedes_cards(HTML + HTML.replace("Demonstrator", "Pre-Owned").replace(".html", "-used.html"), "OEM", URL, "Mercedes-Benz E-Class")
    monkeypatch.setattr("src.oem_inventory.fetch_mercedes_inventory", lambda *a: rows)
    result = BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(query="Mercedes-Benz E-Class", condition="demo"))
    assert len(result.listings) == 2
    assert all(r["condition_signal"] == "demo" for r in result.listings)
