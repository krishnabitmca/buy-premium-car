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


def test_mercedes_scroll_uses_advertised_group_count_and_page_budget(monkeypatch):
    seen=[]
    class Response:
        def __init__(self,text):self.text=text
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,size):return self.text.encode()
    class Opener:
        def open(self,request,timeout):
            seen.append(request)
            if request.data is None:return Response(json.dumps({'details':{'security_token1':'public1','security_token2':'public2','security_token2_rand':'public3'}}))
            fields=parse_qs(request.data.decode())
            if 'group_no' in fields:return Response(HTML.replace('.html','-second.html'))
            return Response(HTML+'<input id="tr_load" value="1"><input id="total_groups" value="5">')
    monkeypatch.setattr('src.oem_inventory.urllib.request.build_opener',lambda *a:Opener())
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE','2')
    rows=fetch_mercedes_inventory(URL,'','both','OEM')
    assert len(rows)==4
    assert len(seen)==4
    assert parse_qs(seen[-1].data.decode())['group_no']==['1']
    assert parse_qs(seen[-1].data.decode())['subaction']==['scroll_fltr']


def test_bmw_scroll_is_read_only_bounded_and_deduplicated(monkeypatch):
    from src.oem_inventory import fetch_bmw_inventory
    html='<form><input id="tr_load" value="1"><input id="total_groups" value="5"><input name="token1" value="public"><input name="action" value="unexpected"></form>'
    seen=[]
    row={'url':'https://www.bmwusedcars.in/car/1','price_lakh':30}
    monkeypatch.setattr('src.oem_inventory.lm.parse_bmw_listing_cards',lambda *a:[dict(row)])
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE','2')
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,size):return b'cards'
    class Initial(Response):
        def read(self,size):return html.encode()
    class Opener:
        def open(self,request,timeout):
            if request.data is None:return Initial()
            seen.append(request);return Response()
    monkeypatch.setattr('src.oem_inventory.urllib.request.build_opener',lambda *a:Opener())
    rows=fetch_bmw_inventory('https://www.bmwusedcars.in/buy-used-cars','','OEM',lambda _:html)
    assert rows==[row] and len(seen)==1
    assert parse_qs(seen[0].data.decode())['action']==['xoxo_fetch_buyusedcars_filtersearch']
    assert parse_qs(seen[0].data.decode())['group_no']==['1']
    with pytest.raises(ValueError):fetch_bmw_inventory('https://other.example/stock','','OEM',lambda _:html)


def test_adapter_filters_oem_used_cars_out_of_demo_results(monkeypatch):
    source = {"name": "Mercedes-Benz Used Cars", "adapter_status": "live", "url": URL, "parser_strategy": "mercedes_inventory"}
    monkeypatch.setattr("src.source_adapters.adapter_execution_allowed", lambda _: True)
    monkeypatch.setattr("src.source_adapters.record_adapter_execution", lambda *a, **kw: None)
    rows = parse_mercedes_cards(HTML + HTML.replace("Demonstrator", "Pre-Owned").replace(".html", "-used.html"), "OEM", URL, "Mercedes-Benz E-Class")
    monkeypatch.setattr("src.oem_inventory.fetch_mercedes_inventory", lambda *a: rows)
    result = BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(query="Mercedes-Benz E-Class", condition="demo"))
    assert len(result.listings) == 2
    assert all(r["condition_signal"] == "demo" for r in result.listings)


@pytest.mark.parametrize('kind', ['bmw', 'mercedes'])
def test_oem_adapter_resumes_all_scroll_groups_without_persisting_tokens(monkeypatch, kind):
    host = 'www.bmwusedcars.in' if kind == 'bmw' else 'www.mercedes-benzusedcar.in'
    url = 'https://' + host + '/buy-used-cars'
    metadata = '<form><input id="tr_load" value="1"><input id="total_groups" value="5"><input name="token1" value="session-only"></form>'
    groups = []
    class Response:
        def __init__(self, text): self.text = text
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return self.text.encode()
    class Opener:
        def open(self, request, timeout):
            if request.data is None:
                if 'get_tokens' in request.full_url:
                    return Response(json.dumps({'details': dict(security_token1='session-only', security_token2='two', security_token2_rand='three')}))
                return Response(HTML + metadata)
            fields = parse_qs(request.data.decode())
            if 'group_no' not in fields: return Response(HTML + metadata)
            group = int(fields['group_no'][0])
            groups.append(group)
            return Response(HTML.replace('.html', f'-group-{group}.html') + f'<!--group-{group}-->')
    monkeypatch.setattr('src.oem_inventory.urllib.request.build_opener', lambda *a: Opener())
    monkeypatch.setattr('src.source_adapters.fetch_text', lambda _: HTML + metadata)
    monkeypatch.setattr('src.oem_inventory.lm.parse_bmw_listing_cards', lambda html, *args: [
        {'url': url + '/' + ('0' if '<!--group-' not in html else html.split('<!--group-')[1].split('-->')[0]),
         'brand': 'BMW', 'model': 'X1', 'price_lakh': 30, 'condition_signal': 'used'}])
    monkeypatch.setattr('src.source_adapters.adapter_execution_allowed', lambda _: True)
    monkeypatch.setattr('src.source_adapters.record_adapter_execution', lambda *a, **kw: None)
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE', '2')
    adapter = BuiltinMarketplaceAdapter({'name': 'OEM', 'url': url,
        'parser_strategy': 'bmw_cards' if kind == 'bmw' else 'mercedes_inventory'})
    progress = {}
    pages = 0
    listings = []
    for _ in range(3):
        result = adapter.fetch(AdapterRequest(continuation=progress))
        assert result.status == 'live' and result.pages_fetched <= 2
        pages += result.pages_fetched
        listings.extend(result.listings)
        progress = result.continuation
        assert 'session-only' not in json.dumps(progress)
        if progress is None: break
    assert progress is None and pages == 5 and groups == [1, 2, 3, 4]
    assert len({row['url'] for row in listings}) == (5 if kind == 'bmw' else 10)


def test_missing_or_empty_scroll_metadata_cannot_complete_a_resume():
    from bs4 import BeautifulSoup
    from src.oem_inventory import _scroll_batch
    with pytest.raises(RuntimeError, match='metadata disappeared'):
        _scroll_batch([], BeautifulSoup('', 'html.parser'), {'next_group': 2}, 2, lambda _: '', lambda _: [])
    soup = BeautifulSoup('<input id="tr_load" value="1"><input id="total_groups" value="5">', 'html.parser')
    with pytest.raises(RuntimeError, match='empty content'):
        _scroll_batch([], soup, {'next_group': 2}, 2, lambda _: '', lambda _: [])
