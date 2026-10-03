from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

from api.catalog import handler as CatalogHandler
from api.search import handler as SearchHandler

ROOT = Path(__file__).resolve().parent


class RenderHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_OPTIONS(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/catalog"):
            return CatalogHandler.do_OPTIONS(self)
        if path.startswith("/api/search"):
            return SearchHandler.do_OPTIONS(self)
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/catalog":
            return CatalogHandler.do_GET(self)
        if path == "/api/search":
            return SearchHandler.do_GET(self)
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/search":
            return SearchHandler.do_POST(self)
        self.send_error(404, "Not found")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer(("0.0.0.0", port), RenderHandler)
    print(f"CarScanner listening on 0.0.0.0:{port}", flush=True)
    server.serve_forever()
