import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from api import search
from render_server import RenderHandler

@pytest.fixture
def preview():
    server = ThreadingHTTPServer(('127.0.0.1', 0), RenderHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:' + str(server.server_port)
    server.shutdown()
    server.server_close()
    thread.join()

@pytest.mark.parametrize('path', ['/.env', '/src/inventory_db.py', '/.git/config', '/supabase/migrations/001_deal_watch.sql'])
def test_preview_does_not_expose_server_files(preview, path):
    with pytest.raises(HTTPError) as exc:
        urlopen(preview + path, timeout=5)
    assert exc.value.code == 404

def test_catalog_preflight_and_watch_routes(preview):
    with urlopen(Request(preview + '/api/catalog', method='OPTIONS'), timeout=5) as response:
        assert response.status == 204
    for method in ('GET', 'PATCH', 'DELETE'):
        try:
            response = urlopen(Request(preview + '/api/watch', method=method), timeout=5)
        except HTTPError as response:
            assert response.code == 401
        else:
            assert method == 'GET' and response.status == 200
            response.close()

def test_empty_inventory_respects_disabled_live_fallback(preview, monkeypatch):
    monkeypatch.setenv('CARSCANNER_ALLOW_LIVE_COVERAGE_FALLBACK', 'false')
    monkeypatch.setattr(search, 'inventory_enabled', lambda: True)
    monkeypatch.setattr(search, 'source_db_enabled', lambda: False)
    monkeypatch.setattr(search, 'load_source_registry', lambda: [])
    monkeypatch.setattr(search, 'plan_sources', lambda **kwargs: [])
    monkeypatch.setattr(search, 'search_inventory', lambda **kwargs: ([], [], 0))
    def forbidden(*args, **kwargs):
        pytest.fail('Free preview must not start request-time crawling')
    monkeypatch.setattr(search, 'live_inventory', forbidden)
    request = Request(preview + '/api/search', data=b'{"query":"BMW X1"}', headers={'Content-Type':'application/json'})
    with urlopen(request, timeout=5) as response:
        payload = json.load(response)
    assert payload['mode'] == 'inventory_partial'
    assert payload['results'] == []
    assert 'no live query' in payload['availability_warning']
