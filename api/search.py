from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
import sys
import os
from concurrent.futures import ThreadPoolExecutor

_DEMAND_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="search-demand")

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from src.acquisition import purchase_context
from src.inventory_db import enabled as inventory_enabled, search_inventory
from src.india_geo import infer_state
from src.live_marketplaces import live_inventory, _query_parts, _identity_matches_query
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
    """Return listing-level condition only; source identity is never evidence."""
    explicit=str(v.get("condition_signal") or v.get("condition") or "").strip().lower()
    if explicit in {"demo","demonstrator"}:
        return "demo"
    if explicit=="used":
        return "used"
    return "unknown"

def _match(v,query,budget_min,budget_max,max_age,destination,condition="both"):
    wanted_condition=str(condition or "both").strip().lower()
    actual_condition=_vehicle_condition(v)
    if wanted_condition in {"used","demo"} and actual_condition != wanted_condition:
        return False
    if query and not _identity_matches_query(v, query): return False
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

def _planned_live_sources_unavailable(source_plan, sources):
    """Return true only when configured live sources exist but none responded live.

    A condition such as demo/Jaguar can legitimately have no live source
    configured. That should be a successful empty search, not an HTTP 503.
    A configured live source set that all failed is a real availability error.
    """
    planned_live = {
        str(p.get("name"))
        for p in source_plan
        if p.get("adapter_status") == "live" and p.get("name")
    }
    observed_live = {
        str(s.get("name") or s.get("source"))
        for s in sources
        if s.get("status") == "live" and (s.get("name") or s.get("source"))
    }
    return bool(planned_live) and not planned_live.intersection(observed_live)

def _zero_result_reason(*, result_count, source_plan, sources, search_mode, availability_warning):
    if result_count:
        return None
    if availability_warning:
        return "sources_unavailable"
    if not source_plan:
        return "no_eligible_sources"
    if search_mode == "inventory_partial":
        return "partial_coverage"
    if search_mode in {"live_fallback", "live_coverage_fallback"} and not sources:
        return "sources_unavailable"
    return "no_matching_inventory"

def _score(v):
    # Metasearch relevance: deal evidence + provider choice + trust/completeness.
    deal=float(v.get("discount_pct") or 0)
    sources=int(v.get("source_count") or len(v.get("offers") or []) or 1)
    confidence=float(v.get("identity_confidence") or 0)
    verified=1 if v.get("live_verified") and v.get("data_consistent") else 0
    lowkm=1 if v.get("km") is not None and float(v["km"])<=30000 else 0
    owners=1 if v.get("owners")==1 else 0
    images=1 if (v.get("images") or v.get("image_urls")) else 0
    certified=1 if v.get("certification") else 0
    freshness=1 if v.get("observed_at") else 0
    return (4*max(-10,min(20,deal))+5*min(4,sources)+10*confidence+8*verified+
            5*lowkm+4*owners+3*images+3*certified+4*freshness)

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self): _response(self,204,{})
    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path!="/api/search":
            return _response(self,404,{"error":"Not found"})
        try:
            from urllib.parse import parse_qs
            params=parse_qs(parsed.query)
            query=str((params.get("query") or [""])[0]).strip()
            condition=str((params.get("condition") or ["both"])[0]).strip()
            destination=str((params.get("destination") or [""])[0]).strip()
            vehicles,sources=live_inventory(query,condition,destination=destination)
            return _response(self,200,{"ok":True,"mode":"live","search_scope":"india","query":query,"condition":condition,"vehicles_count":len(vehicles),"sources":sources})
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
            page=max(1, int(body.get("page") or 1))
            page_size=max(1, min(int(body.get("page_size") or 50), 200))
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
            inventory_total = None
            if inventory_enabled():
                inventory_result = search_inventory(
                    query=query,
                    condition=condition,
                    budget_min=budget_min,
                    budget_max=budget_max,
                    max_age_years=max_age,
                    limit=page_size,
                    offset=(page - 1) * page_size,
                    return_count=True,
                )
                vehicles, sources, inventory_total = inventory_result
                expected_live_sources = {
                    str(p.get("name"))
                    for p in source_plan
                    if p.get("adapter_status") == "live"
                }
                inventory_sources = {
                    str(s.get("name") or s.get("source"))
                    for s in sources
                    if s.get("name") or s.get("source")
                }
                coverage_complete = bool(expected_live_sources) and expected_live_sources.issubset(inventory_sources)

                if vehicles and coverage_complete:
                    search_mode = "inventory"
                else:
                    # During inventory warm-up, do not silently present a partial
                    # snapshot as the whole market. If one or more applicable live
                    # sources are missing from inventory, query the live source set.
                    # Once background refresh establishes complete source coverage,
                    # customer traffic becomes inventory-only again.
                    allow_coverage_fallback = os.getenv(
                        "CARSCANNER_ALLOW_LIVE_COVERAGE_FALLBACK", "true"
                    ).lower() not in {"0", "false", "no"}
                    if vehicles and not allow_coverage_fallback:
                        search_mode = "inventory_partial"
                    else:
                        vehicles, sources = live_inventory(
                            query, condition, budget_min, budget_max, destination
                        )
                        search_mode = "live_coverage_fallback" if vehicles else "live_fallback"
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
            availability_warning = None
            if not vehicles and sources and _planned_live_sources_unavailable(source_plan, sources):
                availability_warning = "No configured live source responded for this search; zero results are not an inventory guarantee."
            results=[]
            for v in vehicles:
                if not _match(v,query,budget_min,budget_max,max_age,destination,body.get("condition") or "both"): continue
                enriched=dict(v)
                if enriched.get("image_urls") and not enriched.get("images"):
                    enriched["images"] = enriched["image_urls"]
                    enriched["image"] = enriched["image_urls"][0] if enriched["image_urls"] else None
                enriched["purchase_context"]=purchase_context(v,destination)
                results.append(enriched)
            # Calculate market reference only from comparable live observations.
            from statistics import median
            groups={}
            for v in results:
                key=(str(v.get("brand") or "").strip().lower(),str(v.get("model") or "").strip().lower(),_vehicle_condition(v),str(v.get("price_basis") or "unspecified"))
                price=v.get("price_lakh")
                if key[0] and key[1] and price is not None:
                    groups.setdefault(key,[]).append(float(price))
            for v in results:
                key=(str(v.get("brand") or "").strip().lower(),str(v.get("model") or "").strip().lower(),_vehicle_condition(v),str(v.get("price_basis") or "unspecified"))
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
                # Score only after comparable-price enrichment so deal evidence
                # participates in ranking rather than being calculated too early.
                v["_search_score"]=_score(v)
            results.sort(key=lambda x:(-x["_search_score"],x.get("price_lakh") or 9999))
            for v in results: v.pop("_search_score",None)
            zero_result_reason=_zero_result_reason(
                result_count=len(results), source_plan=source_plan, sources=sources,
                search_mode=search_mode, availability_warning=availability_warning,
            )
            return _response(self,200,{
                "ok":True,
                "search_scope":"india",
                "destination":destination or None,
                "destination_state":infer_state(destination,destination) if destination else None,
                "mode":search_mode,
                "live_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                "sources":sources,
                "source_strategy":summarize_plan(source_plan),
                "source_plan":[{k:p.get(k) for k in ("name","source_type","adapter_status","score","query_strategy","query","reasons")} for p in source_plan[:12]],
                "total_results": int(inventory_total) if search_mode == "inventory" and inventory_total is not None else len(results),
                "page": page,
                "page_size": page_size,
                "has_more": ((page * page_size) < int(inventory_total)) if search_mode == "inventory" and inventory_total is not None else False,
                "inventory_total": int(inventory_total) if inventory_total is not None else None,
                "sources_found":len({offer.get("source") for v in results for offer in (v.get("offers") or [{"source":v.get("source")}]) if offer.get("source")}),
                "search_diagnostics":{
                    "planned_sources":len(source_plan),
                    "responding_sources":len([source for source in sources if source.get("status") in ("live","inventory")]),
                    "result_count":len(results),
                    "zero_result":len(results)==0,
                    "zero_result_reason":zero_result_reason,
                    "coverage_mode":search_mode,
                    "availability_warning":availability_warning,
                },
                "availability_warning": availability_warning,
                "results":results
            })
        except ValueError as exc:
            return _response(self,400,{"error":str(exc)})
        except Exception as exc:
            return _response(self,500,{"error":f"Search failed: {exc}"})
