from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs,urlparse
from src.live_marketplaces import live_brands,live_models

def response(h,status,payload):
    raw=json.dumps(payload,ensure_ascii=False).encode()
    h.send_response(status)
    h.send_header("Content-Type","application/json; charset=utf-8")
    h.send_header("Cache-Control","no-store, max-age=0")
    h.send_header("Access-Control-Allow-Origin","*")
    h.end_headers();h.wfile.write(raw)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path!="/api/catalog":
            return response(self,404,{"error":"Not found"})
        try:
            q=parse_qs(urlparse(self.path).query)
            brand=(q.get("brand") or [""])[0].strip()
            if brand:
                models=live_models(brand)
                return response(self,200,{"ok":True,"mode":"live","source":"CarDekho current catalog","brand":brand,"models":models})
            brands=live_brands()
            return response(self,200,{"ok":True,"mode":"live","source":"CarDekho current catalog","brands":brands})
        except Exception as exc:
            return response(self,502,{"ok":False,"mode":"live","error":f"Live catalog unavailable: {exc}"})
