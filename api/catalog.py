from __future__ import annotations
import json
import re
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs,urlparse
from src.live_marketplaces import live_brands,live_models
from src.car_catalog import CAR_MAKES

_NON_MODEL_NAMES = {
    "images","image","gallery","galleries","photos","photo","videos","video",
    "reviews","review","news","offers","offer","dealers","dealer","service",
    "compare","accessories","view all models","all models",
}

# Public catalogue metadata only. Never cache listing prices or availability.
_model_cache=OrderedDict()
_model_cache_lock=threading.Lock()
_model_load_locks=[threading.Lock() for _ in range(16)]


def catalog_models(brand):
    key=brand.strip().casefold()
    # Fixed lock stripes and a bounded LRU prevent arbitrary query growth.
    with _model_load_locks[hash(key)%len(_model_load_locks)]:
        now=time.monotonic()
        with _model_cache_lock:
            cached=_model_cache.get(key)
            if cached and cached[0]>now:
                _model_cache.move_to_end(key)
                return [dict(row) for row in cached[1]]
        models=_sanitize_models(live_models(brand))
        if models:
            with _model_cache_lock:
                _model_cache[key]=(time.monotonic()+900,models)
                _model_cache.move_to_end(key)
                while len(_model_cache)>64:
                    _model_cache.popitem(last=False)
        # Empty/error responses never poison the successful metadata cache.
        return [dict(row) for row in models]

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
                models=catalog_models(brand)
                return response(self,200,{"ok":True,"mode":"live","source":"CarDekho current catalog with resilient fallback","brand":brand,"catalog_fallback":any(x.get("catalog_verified")=="fallback" for x in models),"models":models})
            discovered={b['name']:b for b in live_brands()}
            brands=[discovered.get(name,{'name':name,'catalog_verified':'taxonomy',
                                        'inventory_coverage':'unverified'})
                    for name in sorted(set(CAR_MAKES)|set(discovered))]
            return response(self,200,{"ok":True,"mode":"live",
                "source":"India make taxonomy with discovered catalog metadata",
                "coverage_notice":"A selectable brand does not establish indexed inventory or marketplace coverage.",
                "brands":brands})
        except Exception as exc:
            return response(self,502,{"ok":False,"mode":"live","error":f"Live catalog unavailable: {exc}"})
