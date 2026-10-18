from contextlib import contextmanager
from io import BytesIO
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, BoundedSemaphore
import pytest
from wsgiref.util import setup_testing_defaults

import wsgi


def request(path='/', method='GET', body=b'', **environ):
    env = {}
    setup_testing_defaults(env)
    env.update(PATH_INFO=path, REQUEST_METHOD=method, CONTENT_LENGTH=str(len(body)),
               **{'wsgi.input': BytesIO(body)})
    env.update(environ)
    response = {}
    def start(status, headers):
        response.update(status=int(status.split()[0]), headers=dict(headers))
    response['body'] = b''.join(wsgi.application(env, start))
    return response


def test_shared_public_routes_and_private_file_allowlist():
    home = request()
    assert home['status'] == 200 and b'CarScanner' in home['body']
    assert home['headers']['X-CarScanner-Runtime'] == 'wsgi'
    assert request('//', QUERY_STRING='qa=fixture')['body'] == home['body']
    assert request('/health')['body'] == b'ok'
    assert request('/index.html', 'HEAD')['body'] == b''
    for path in ('/.env', '/config/sources.yaml', '/src/source_registry_db.py', '/../.env'):
        assert request(path)['status'] == 404


def test_search_uses_shared_handler_and_preserves_json_timing_and_query(monkeypatch):
    from api.search import _read_json, _response
    def search(handler):
        value = _read_json(handler)
        assert handler.headers.get('Authorization') == 'Bearer fixture'
        assert handler.path == '/api/search?trace=fixture'
        _response(handler, 200, {'query': value['query'], 'search_engine': 'postgresql'})
    monkeypatch.setattr('render_server.SearchHandler.do_POST', search)
    result = request('/api/search', 'POST', b'{"query":"Honda"}',
                     QUERY_STRING='trace=fixture', HTTP_AUTHORIZATION='Bearer fixture',
                     CONTENT_TYPE='application/json')
    assert json.loads(result['body']) == {'query': 'Honda', 'search_engine': 'postgresql'}
    assert result['headers']['Cache-Control'] == 'no-store'
    assert int(result['headers']['Content-Length']) == len(result['body'])


@pytest.mark.parametrize('length,status', [('bad', 400), ('-1', 400), ('65537', 413)])
def test_body_size_and_length_are_rejected_before_reading(length, status):
    class Unreadable:
        def read(self, *_):
            raise AssertionError('Rejected bodies must not be read')
    result = request('/api/search', 'POST', CONTENT_LENGTH=length, **{'wsgi.input': Unreadable()})
    assert result['status'] == status


def test_readiness_failure_does_not_change_liveness_and_never_exposes_error(monkeypatch):
    monkeypatch.setattr(wsgi, 'enabled', lambda: True)
    def fail(**kwargs):
        assert kwargs == {'checkout_timeout': 1}
        raise RuntimeError('credential-that-must-not-escape')
    monkeypatch.setattr(wsgi, '_connect', fail)
    assert request('/ready')['status'] == 503
    assert b'credential' not in request('/ready')['body']
    assert request('/health')['status'] == 200


def test_readiness_checks_canonical_tables_and_recovers(monkeypatch):
    monkeypatch.setattr(wsgi, 'enabled', lambda: True)
    statements = []
    class Database:
        def execute(self, statement):
            statements.append(statement)
            return self
        def fetchone(self):
            return {'ready': True}
    @contextmanager
    def connect(**kwargs):
        assert kwargs['checkout_timeout'] == 1
        yield Database()
    monkeypatch.setattr(wsgi, '_connect', connect)
    assert request('/ready')['status'] == 200
    assert "set local statement_timeout='1000ms'" in statements
    assert 'set transaction read only' in statements
    assert 'public.vehicle_observations' in statements[-1]
    monkeypatch.setattr(wsgi, 'enabled', lambda: False)
    assert request('/ready')['status'] == 503


def test_watch_preflight_mutation_auth_and_errors_share_existing_routes():
    preflight = request('/api/watch', 'OPTIONS')
    assert preflight['status'] == 204 and preflight['body'] == b''
    assert 'PATCH' in preflight['headers']['Access-Control-Allow-Methods']
    assert request('/api/watch', 'DELETE')['status'] == 401
    assert request('/api/search', 'HEAD')['status'] == 405
    assert request('/', 'TRACE')['status'] == 405


def test_uncaught_errors_are_redacted_and_replace_partial_response(monkeypatch):
    def fail(handler):
        handler.wfile.write(b'partial-secret')
        raise RuntimeError('sensitive-input')
    monkeypatch.setattr('render_server.SearchHandler.do_POST', fail)
    result = request('/api/search', 'POST', b'{}')
    assert result['status'] == 500
    assert b'secret' not in result['body'] and b'sensitive' not in result['body']


def test_concurrent_api_overload_is_immediate_and_preserves_health(monkeypatch):
    monkeypatch.setattr(wsgi, 'API_SLOTS', BoundedSemaphore(3))
    entered = Barrier(4)
    release = Event()
    def slow(handler):
        entered.wait(timeout=5)
        assert release.wait(timeout=5)
        handler.wfile.write(b'ok')
    monkeypatch.setattr('render_server.SearchHandler.do_POST', slow)
    class Unreadable:
        def read(self, *_):
            raise AssertionError('Overloaded requests must not read their bodies')
    with ThreadPoolExecutor(max_workers=3) as executor:
        active = [executor.submit(request, '/api/search', 'POST', b'{}') for _ in range(3)]
        try:
            entered.wait(timeout=5)
            busy = request('/api/search', 'POST', CONTENT_LENGTH='2', **{'wsgi.input': Unreadable()})
            assert busy['status'] == 503
            assert busy['headers']['Retry-After'] == '1'
            assert busy['headers']['Cache-Control'] == 'no-store'
            assert request('/health')['status'] == 200
            assert request('/')['status'] == 200
            assert request('/api/version')['status'] == 200
            assert request('/api/watch', 'OPTIONS')['status'] == 204
        finally:
            release.set()
        assert all(future.result()['status'] == 200 for future in active)
    monkeypatch.setattr('render_server.SearchHandler.do_POST', lambda handler: handler.wfile.write(b'recovered'))
    assert request('/api/search', 'POST')['body'] == b'recovered'


def test_admission_released_after_handler_and_response_failures(monkeypatch):
    monkeypatch.setattr(wsgi, 'API_SLOTS', BoundedSemaphore(1))
    def fail(handler):
        raise RuntimeError('fixture')
    monkeypatch.setattr('render_server.SearchHandler.do_POST', fail)
    assert request('/api/search', 'POST')['status'] == 500
    assert request('/api/search', 'POST')['status'] == 500
    env = {'PATH_INFO': '/api/search', 'REQUEST_METHOD': 'POST'}
    def failed_response(*_):
        raise RuntimeError('disconnected')
    with pytest.raises(RuntimeError, match='disconnected'):
        wsgi.application(env, failed_response)
    monkeypatch.setattr('render_server.SearchHandler.do_POST', lambda handler: None)
    assert request('/api/search', 'POST')['status'] == 200


def test_saved_intent_validation_never_calls_generative_model(monkeypatch):
    def forbidden(*_args,**_kwargs):raise AssertionError('Saved searches must not invoke Gemini')
    monkeypatch.setattr('api.intent.interpret',forbidden)
    result=request('/api/intent','POST',json.dumps({'validate_only':True,'query':'Honda City',
                   'budget_max':15,'fuels':['petrol'],'destination':'Bengaluru'}).encode())
    payload=json.loads(result['body'])
    assert result['status']==200 and payload['model_used'] is False
    assert payload['intent']['query']=='Honda City' and payload['intent']['seller_city']==''
    assert request('/api/intent','POST',b'{"validate_only":true,"budget_max":-1}')['status']==400


def test_shortlist_revalidation_limits_ids_and_never_falls_back_to_client_snapshot(monkeypatch):
    calls=[]
    identifier='12345678-1234-1234-1234-123456789012'
    def inventory(**kwargs):
        calls.append(kwargs)
        return [],[]
    monkeypatch.setattr('api.shortlist.search_inventory',inventory)
    result=request('/api/shortlist','POST',json.dumps({'vehicle_ids':[identifier],
                   'price_lakh':1,'results':[{'price_lakh':1}]}).encode())
    payload=json.loads(result['body'])
    assert payload['results']==[] and payload['unavailable_vehicle_ids']==[identifier]
    assert calls==[{'_vehicle_ids':[identifier],'limit':2000,'require_persistence':True}]
    for body in ({'vehicle_ids':['bad']},{'vehicle_ids':[identifier]*7},{'vehicle_ids':'bad'}):
        assert request('/api/shortlist','POST',json.dumps(body).encode())['status']==400
    def fail(**_kwargs):raise RuntimeError('credential-must-not-escape')
    monkeypatch.setattr('api.shortlist.search_inventory',fail)
    result=request('/api/shortlist','POST',json.dumps({'vehicle_ids':[identifier]}).encode())
    assert result['status']==503 and b'credential' not in result['body']


def test_warming_model_catalogue_is_retryable_without_blocking_http(monkeypatch):
    from api.catalog import CatalogPending
    def pending(_):raise CatalogPending()
    monkeypatch.setattr('api.catalog.catalog_models',pending)
    result=request('/api/catalog',QUERY_STRING='brand=BMW')
    assert result['status']==503 and result['headers']['Retry-After']=='1'
    assert result['headers']['Cache-Control']=='no-store, max-age=0'


def test_only_declared_public_mobile_shell_assets_are_served():
    for path,content_type in (('/sw.js','text/javascript'),('/manifest.webmanifest','application/manifest+json'),
                              ('/app-icon.svg','image/svg+xml'),('/buyer_state.js','text/javascript')):
        result=request(path)
        assert result['status']==200 and result['headers']['Content-Type'].startswith(content_type)
        assert result['headers']['Cache-Control']=='no-cache'
        assert request(path,'HEAD')['body']==b''
    assert request('/.env')['status']==404
    assert request('/src/buyer_ai.py')['status']==404
