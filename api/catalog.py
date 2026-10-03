from __future__ import annotations
import json
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs,urlparse
from src.live_marketplaces import live_brands,live_models

_NON_MODEL_NAMES = {
    "images","image","gallery","galleries","photos","photo","videos","video",
    "reviews","review","news","offers","offer","dealers","dealer","service",
    "compare","accessories","view all models","all models",
}

def _sanitize_models(models):
    """Defense-in-depth: never expose source navigation as customer models."""
    result=[]
    seen=set()
    for item in models or []:
        if not isinstance(item,dict):
            continue
        name=" ".join(str(item.get("name") or "").split()).strip()
        url=str(item.get("url") or "").strip()
        if not name or name.lower() in _NON_MODEL_NAMES:
            continue
        path=urlparse(url).path.lower().rstrip("/")
        if any(token in path.split("/") for token in {
            "gallery","images","photos","photo","videos","video","reviews",
            "review","news","offers","offer","dealers","dealer","service",
            "compare","accessories"
        }):
            continue
        key=str(item.get("slug") or re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-"))
        if key in seen:
            continue
        seen.add(key)
        result.append({**item,"name":name,"slug":key})
    return sorted(result,key=lambda x:x["name"].lower())

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
                models=_sanitize_models(live_models(brand))
                return response(self,200,{"ok":True,"mode":"live","source":"CarDekho current catalog with resilient fallback","brand":brand,"catalog_fallback":any(x.get("catalog_verified")=="fallback" for x in models),"models":models})
            brands=live_brands()
            return response(self,200,{"ok":True,"mode":"live","source":"CarDekho current catalog","brands":brands})
        except Exception as exc:
            return response(self,502,{"ok":False,"mode":"live","error":f"Live catalog unavailable: {exc}"})
