from contextlib import contextmanager
from io import BytesIO
import json
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
