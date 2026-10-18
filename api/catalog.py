from __future__ import annotations
import json
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
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
_model_refresh=ThreadPoolExecutor(max_workers=2,thread_name_prefix='model-catalog')
_model_pending=set()


def observed_models(brand):
    """Names are metadata, including discontinued models; never proof of stock."""
    from src.source_registry_db import enabled,_connect
    if not enabled():return []
    try:
        with _connect() as conn,conn.cursor() as cur:
            cur.execute("""select distinct v.model as name from vehicles v
                where lower(v.brand)=lower(%s) and length(v.model) between 1 and 100
                and exists(select 1 from listings l join sources s using(source_id)
                    where l.vehicle_id=v.vehicle_id and s.enabled and l.last_verified_at is not null)
                order by v.model limit 500""",(brand,))
            return [{'name':row['name'],'catalog_verified':'observed_inventory'} for row in cur.fetchall()]
    except Exception:
        return []


def _cache_models(key,models):
    with _model_cache_lock:
        _model_cache[key]=(time.monotonic()+900,models)
        _model_cache.move_to_end(key)
        while len(_model_cache)>64:_model_cache.popitem(last=False)


def _refresh_models(key,brand,observed):
    try:
        models=_sanitize_models([*live_models(brand),*observed])
        if models:_cache_models(key,models)
    except Exception:
        pass  # Keep observed model names during an upstream outage.
    finally:
        with _model_cache_lock:_model_pending.discard(key)


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
        observed=_sanitize_models(observed_models(brand))
        if observed:
            _cache_models(key,observed)
            with _model_cache_lock:
                refresh=key not in _model_pending and len(_model_pending)<16
                if refresh:_model_pending.add(key)
            if refresh:_model_refresh.submit(_refresh_models,key,brand,observed)
            return [dict(row) for row in observed]
        models=_sanitize_models(live_models(brand))
        if models:
            _cache_models(key,models)
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
                return response(self,200,{"ok":True,"mode":"live","source":"Observed model metadata with live catalogue enrichment","brand":brand,"catalog_fallback":any(x.get("catalog_verified") in {"fallback","observed_inventory"} for x in models),"models":models})
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
