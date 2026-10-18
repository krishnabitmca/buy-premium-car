"""Production WSGI boundary sharing the existing API handlers and public routes."""
from email.message import Message
from http import HTTPStatus
from io import BytesIO
import json
import logging

from render_server import RenderHandler, ROOT
from src.source_registry_db import _connect, enabled

log = logging.getLogger(__name__)
MAX_BODY_BYTES = 64 * 1024


def readiness():
    """Check the canonical store without fetching inventory or external sources."""
    if not enabled():
        return False
    try:
        with _connect(checkout_timeout=1) as conn:
            conn.execute("set local statement_timeout='1000ms'")
            conn.execute('set transaction read only')
            # LIMIT 0 validates table/column access without reading inventory.
            conn.execute("""select s.source_id,v.vehicle_id,l.listing_id,o.observed_at
                from public.sources s cross join public.vehicles v
                cross join public.listings l cross join public.vehicle_observations o limit 0""")
            return True
    except Exception as exc:
        log.warning('database_readiness_failed type=%s', type(exc).__name__)
        return False


class RequestAdapter(RenderHandler):
    """Translate WSGI input/output; domain logic remains in the shared handlers."""

    def __init__(self, environ, body):
        self.command = environ.get('REQUEST_METHOD', 'GET')
        self.path = environ.get('PATH_INFO', '/') or '/'
        if environ.get('QUERY_STRING'):
            self.path += '?' + environ['QUERY_STRING']
        self.headers = Message()
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                self.headers[key[5:].replace('_', '-')] = value
        for key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            if environ.get(key):
                self.headers[key.replace('_', '-')] = environ[key]
        self.rfile = BytesIO(body)
        self.wfile = BytesIO()
        self.directory = str(ROOT)
        self.response_status = 200
        self.response_headers = []

    def send_response(self, code, message=None):
        self.response_status = int(code)

    def send_header(self, keyword, value):
        self.response_headers.append((str(keyword), str(value)))

    def end_headers(self):
        pass

    def send_error(self, code, message=None, explain=None):
        self.response_status = int(code)
        self.response_headers = [('Content-Type', 'application/json'), ('Cache-Control', 'no-store')]
        self.wfile = BytesIO(json.dumps({'ok': False, 'error': HTTPStatus(code).phrase}).encode())

    def log_message(self, *_args):
        # The process server records method/status/duration without query strings.
        pass


def application(environ, start_response):
    method = environ.get('REQUEST_METHOD', 'GET')
    path = environ.get('PATH_INFO', '/') or '/'
    adapter = RequestAdapter(environ, b'')
    try:
        try:
            length = int(environ.get('CONTENT_LENGTH') or 0)
        except (TypeError, ValueError):
            length = -1
        if length < 0:
            adapter.send_error(400)
        elif length > MAX_BODY_BYTES:
            adapter.send_error(413)
        elif method not in {'GET', 'HEAD', 'POST', 'PATCH', 'DELETE', 'OPTIONS'}:
            adapter.send_error(405)
        elif method in {'GET', 'HEAD'} and path == '/ready':
            ready = readiness()
            adapter.response_status = 200 if ready else 503
            adapter.response_headers = [('Content-Type', 'application/json'), ('Cache-Control', 'no-store')]
            adapter.wfile.write(json.dumps({'ok': ready, 'database': 'ready' if ready else 'unavailable'}).encode())
        elif method == 'HEAD':
            # HEAD shares only the static/liveness/version routes, not API work.
            if path not in {'/', '/index.html', '/health', '/api/version', '/favicon.ico'}:
                adapter.send_error(405)
            else:
                adapter.do_GET()
        else:
            adapter.rfile = BytesIO(environ['wsgi.input'].read(length)) if length else BytesIO()
            getattr(adapter, 'do_' + method)()
    except Exception as exc:
        # Handler exceptions must not disclose URLs, inputs, credentials or traces.
        log.error('http_request_failed type=%s', type(exc).__name__)
        adapter.send_error(500)
    payload = adapter.wfile.getvalue()
    headers = [(key, value) for key, value in adapter.response_headers
               if key.lower() not in {'content-length', 'connection', 'transfer-encoding'}]
    headers.append(('X-CarScanner-Runtime', 'wsgi'))
    if adapter.response_status in {204, 304}:
        payload = b''
    else:
        headers.append(('Content-Length', str(len(payload))))
    start_response(f'{adapter.response_status} {HTTPStatus(adapter.response_status).phrase}', headers)
    return [b'' if method == 'HEAD' else payload]
