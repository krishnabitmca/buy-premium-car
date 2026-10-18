from __future__ import annotations

import os
import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from api.catalog import handler as CatalogHandler
from api.search import handler as SearchHandler
from api.watch import handler as WatchHandler
from api.intent import handler as IntentHandler
from api.shortlist import handler as ShortlistHandler

ROOT = Path(__file__).resolve().parent


class CarScannerServer(ThreadingHTTPServer):
    # A browser burst can exceed the stdlib default of five pending sockets.
    request_queue_size = 128


class RenderHandler(SimpleHTTPRequestHandler):
    _watch_mutation = WatchHandler._watch_mutation

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_OPTIONS(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/watch":
            return WatchHandler.do_OPTIONS(self)
        if path in {"/api/catalog", "/api/search", "/api/intent", "/api/shortlist"}:
            return SearchHandler.do_OPTIONS(self)
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == '/api/version':
            commit = os.getenv('RENDER_GIT_COMMIT', '')
            raw = json.dumps({'ok': True, 'commit': commit if re.fullmatch(r'[0-9a-f]{40}', commit) else None}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/api/catalog":
            return CatalogHandler.do_GET(self)
        if path == "/api/search":
            return SearchHandler.do_GET(self)
        if path == "/api/watch":
            return WatchHandler.do_GET(self)
        if path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        if path == "/":
            self.path = "/index.html"
        elif path not in {"/index.html", "/buyer_state.js"}:
            return self.send_error(404, "Not found")
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == '/api/intent':
            return IntentHandler.do_POST(self)
        if path == '/api/shortlist':
            return ShortlistHandler.do_POST(self)
        if path == "/api/search":
            return SearchHandler.do_POST(self)
        if path == "/api/watch":
            return WatchHandler.do_POST(self)
        self.send_error(404, "Not found")

    def do_PATCH(self):
        if self.path.split("?", 1)[0] == "/api/watch":
            return WatchHandler.do_PATCH(self)
        self.send_error(404, "Not found")

    def do_DELETE(self):
        if self.path.split("?", 1)[0] == "/api/watch":
            return WatchHandler.do_DELETE(self)
        self.send_error(404, "Not found")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = CarScannerServer((host, port), RenderHandler)
    print(f"CarScanner listening on {host}:{port}", flush=True)
    server.serve_forever()
