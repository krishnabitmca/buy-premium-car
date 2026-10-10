from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

from api.catalog import handler as CatalogHandler
from api.search import handler as SearchHandler
from api.watch import handler as WatchHandler

ROOT = Path(__file__).resolve().parent


class RenderHandler(SimpleHTTPRequestHandler):
    _watch_mutation = WatchHandler._watch_mutation

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_OPTIONS(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/watch":
            return WatchHandler.do_OPTIONS(self)
        if path in {"/api/catalog", "/api/search"}:
            return SearchHandler.do_OPTIONS(self)
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
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
        if path == "/":
            self.path = "/index.html"
        elif path != "/index.html":
            return self.send_error(404, "Not found")
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
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
    from http.server import ThreadingHTTPServer
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), RenderHandler)
    print(f"CarScanner listening on {host}:{port}", flush=True)
    server.serve_forever()
