from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from src.acquisition import purchase_context
from src.india_geo import infer_state

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

def _vehicle_condition(v):
    return str(v.get("condition_signal") or "").lower() or ("demo" if "demo" in (str(v.get("variant",""))+" "+str(v.get("source",""))).lower() else "used")

def _match(v,query,budget_min,budget_max,max_age,destination):
    hay=" ".join(str(v.get(k) or "") for k in ("brand","model","variant","location","fuel","transmission","source")).lower()
    tokens=[t for t in query.lower().split() if t]
    if tokens and not all(t in hay for t in tokens): return False
    price=v.get("price_lakh")
    if budget_min is not None and (price is None or float(price)<budget_min): return False
    if budget_max is not None and (price is None or float(price)>budget_max): return False
    if max_age is not None:
        year=v.get("mfg_year")
        if year is None or int(year)<2026-int(max_age): return False
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
            data=json.loads((ROOT/"data/latest.json").read_text(encoding="utf-8"))
            return _response(self,200,{"ok":True,"search_scope":"india","vehicles_count":len(data.get("vehicles",[])),"run_date":data.get("run_date")})
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
            data=json.loads((ROOT/"data/latest.json").read_text(encoding="utf-8"))
            results=[]
            for v in data.get("vehicles",[]):
                if not _match(v,query,budget_min,budget_max,max_age,destination): continue
                enriched=dict(v)
                enriched["purchase_context"]=purchase_context(v,destination)
                enriched["_search_score"]=_score(v)
                results.append(enriched)
            results.sort(key=lambda x:(-x["_search_score"],x.get("price_lakh") or 9999))
            for v in results: v.pop("_search_score",None)
            return _response(self,200,{
                "ok":True,
                "search_scope":"india",
                "destination":destination or None,
                "destination_state":infer_state(destination,destination) if destination else None,
                "run_date":data.get("run_date"),
                "total_results":len(results),
                "sources_found":len({s for v in results for s in [v.get("source")] if s}),
                "results":results
            })
        except ValueError as exc:
            return _response(self,400,{"error":str(exc)})
        except Exception as exc:
            return _response(self,500,{"error":f"Search failed: {exc}"})
