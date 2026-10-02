from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
import sys
from concurrent.futures import ThreadPoolExecutor

_DEMAND_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="search-demand")

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from src.acquisition import purchase_context
from src.inventory_db import enabled as inventory_enabled, search_inventory
from src.india_geo import infer_state
from src.live_marketplaces import live_inventory, _query_parts
from src.source_intelligence import load_source_registry, plan_sources, summarize_plan
from src.source_registry_db import enabled as source_db_enabled, record_search_demand

def _read_json(handler):
    length=int(handler.headers.get("Content-Length","0"))
    if length<=0 or length>64_000: raise ValueError("Request body is missing or too large")
    return json.loads(handler.rfile.read(length).decode("utf-8"))

def _response(handler,status,payload):
    raw=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type","application/json; charset=utf-8")
    handler.send_header("Cache-Control","no-store")
    handler.send_header("Access-Control-Allow-Origin","*")
    handler.send_header("Access-Control-Allow-Headers","Content-Type")
    handler.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(raw)


def _budget_band(budget_min, budget_max):
    ceiling = budget_max if budget_max is not None else budget_min
    if ceiling is None:
        return "unspecified"
    if ceiling <= 15:
        return "0-15"
    if ceiling <= 40:
        return "15-40"
    if ceiling <= 100:
        return "40-100"
    return "100+"

def _vehicle_condition(v):
    explicit=str(v.get("condition_signal") or "").strip().lower()
    if explicit in {"used","demo","demonstrator"}:
        return "demo" if explicit=="demonstrator" else explicit
    return "demo" if "demo" in (str(v.get("variant",""))+" "+str(v.get("source",""))).lower() else "used"

def _match(v,query,budget_min,budget_max,max_age,destination,condition="both"):
    wanted_condition=str(condition or "both").strip().lower()
    actual_condition=_vehicle_condition(v)
    if wanted_condition in {"used","demo"} and actual_condition != wanted_condition:
        return False
    hay=" ".join(str(v.get(k) or "") for k in ("brand","model","listing_name","variant","location","fuel","transmission","source")).lower()
    tokens=[t for t in query.lower().split() if t]
    if tokens and not all(t in hay for t in tokens): return False
    price=v.get("price_lakh")
    if budget_min is not None and (price is None or float(price)<budget_min): return False
    if budget_max is not None and (price is None or float(price)>budget_max): return False
    if max_age is not None:
        year=v.get("mfg_year")
        if year is None or int(year)<datetime.now().year-int(max_age): return False
    if destination:
        # Destination is not a geographic restriction. It is used only to annotate
        # local/same-state/interstate purchase context.
        return True
    return True

def _score(v):
    # Transparent ordering: deal evidence first, then identity and trust signals.
    deal=float(v.get("discount_pct") or 0)
    sources=int(v.get("source_count") or 1)
    confidence=float(v.get("identity_confidence") or 0)
    verified=1 if v.get("live_verified") and v.get("data_consistent") else 0
    lowkm=1 if v.get("km") is not None and float(v["km"])<=30000 else 0
    owners=1 if v.get("owners")==1 else 0
    return 4*max(-10,min(20,deal))+5*min(4,sources)+10*confidence+8*verified+5*lowkm+4*owners

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self): _response(self,204,{})
    def do_GET(self):
        if urlparse(self.path).path!="/api/search":
            return _response(self,404,{"error":"Not found"})
        try:
            vehicles,sources=live_inventory()
            return _response(self,200,{"ok":True,"mode":search_mode,"search_scope":"india","vehicles_count":len(vehicles),"sources":sources})
        except Exception as exc:
            return _response(self,500,{"error":f"Search inventory unavailable: {exc}"})
    def do_POST(self):
        if urlparse(self.path).path!="/api/search":
            return _response(self,404,{"error":"Not found"})
        try:
            body=_read_json(self)
            query=str(body.get("query") or "").strip()
            destination=str(body.get("destination") or "").strip()
            budget_min=float(body["budget_min"]) if body.get("budget_min") not in (None,"") else None
            budget_max=float(body["budget_max"]) if body.get("budget_max") not in (None,"") else None
            max_age=float(body["max_age_years"]) if body.get("max_age_years") not in (None,"") else None
            if budget_min is not None and budget_max is not None and budget_min>budget_max:
                return _response(self,400,{"error":"Minimum budget cannot exceed maximum budget"})
            condition=str(body.get("condition") or "both")
            source_plan=plan_sources(
                brand=_query_parts(query)[0],
                model=_query_parts(query)[1],
                condition=condition,
                budget_min=budget_min,
                budget_max=budget_max,
                destination=destination,
                registry=load_source_registry(),
            )
            search_mode = "live"
            if inventory_enabled():
                vehicles, sources = search_inventory(
                    query=query,
                    condition=condition,
                    budget_min=budget_min,
                    budget_max=budget_max,
                    max_age_years=max_age,
                )
                if vehicles:
                    search_mode = "inventory"
                else:
                    # Transitional fallback while the background ingestion fleet is
                    # warming up. Once inventory coverage is healthy this path should
                    # be disabled to prevent cache-miss fanout to marketplaces.
                    vehicles, sources = live_inventory(
                        query, condition, budget_min, budget_max, destination
                    )
                    search_mode = "live_fallback"
            else:
                vehicles, sources = live_inventory(
                    query, condition, budget_min, budget_max, destination
                )
            if source_db_enabled():
                parts = _query_parts(query)
                state = infer_state(destination, destination) if destination else ""
                _DEMAND_EXECUTOR.submit(
                    record_search_demand,
                    brand=parts[0],
                    model=parts[1],
                    condition=condition,
                    budget_band=_budget_band(budget_min, budget_max),
                    destination_state=state,
                    inventory_hit_count=len(vehicles),
                    source_count=len(sources),
                )
            if not vehicles and sources and not any(s.get("status") == "live" for s in sources):
                return _response(self,503,{"error":"Live marketplace sources are currently unavailable","mode":"live","sources":sources})
            results=[]
            for v in vehicles:
                if not _match(v,query,budget_min,budget_max,max_age,destination,body.get("condition") or "both"): continue
                enriched=dict(v)
                enriched["purchase_context"]=purchase_context(v,destination)
                enriched["_search_score"]=_score(v)
                results.append(enriched)
            # Calculate market reference only from comparable live observations.
            from statistics import median
            groups={}
            for v in results:
                key=(str(v.get("brand") or "").strip().lower(),str(v.get("model") or "").strip().lower(),_vehicle_condition(v))
                price=v.get("price_lakh")
                if key[0] and key[1] and price is not None:
                    groups.setdefault(key,[]).append(float(price))
            for v in results:
                key=(str(v.get("brand") or "").strip().lower(),str(v.get("model") or "").strip().lower(),_vehicle_condition(v))
                comparable=groups.get(key,[])
                if len(comparable)>=3 and v.get("price_lakh") is not None:
                    ref=round(float(median(comparable)),2)
                    v["comp_median"]=ref
                    v["comparable_count"]=len(comparable)
                    v["discount_pct"]=round((ref-float(v["price_lakh"]))/ref*100,1) if ref else None
                else:
                    v["comp_median"]=None
                    v["comparable_count"]=len(comparable)
                    v["discount_pct"]=None
            results.sort(key=lambda x:(-x["_search_score"],x.get("price_lakh") or 9999))
            for v in results: v.pop("_search_score",None)
            return _response(self,200,{
                "ok":True,
                "search_scope":"india",
                "destination":destination or None,
                "destination_state":infer_state(destination,destination) if destination else None,
                "mode":"live",
                "live_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                "sources":sources,
                "source_strategy":summarize_plan(source_plan),
                "source_plan":[{k:p.get(k) for k in ("name","source_type","adapter_status","score","query_strategy","query","reasons")} for p in source_plan[:12]],
                "total_results":len(results),
                "sources_found":len({s for v in results for s in [v.get("source")] if s}),
                "results":results
            })
        except ValueError as exc:
            return _response(self,400,{"error":str(exc)})
        except Exception as exc:
            return _response(self,500,{"error":f"Search failed: {exc}"})
