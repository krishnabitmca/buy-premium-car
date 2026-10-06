"""Live catalog matrix verification.

Enumerates the live brand/model catalog and probes every model against every
configured live source. This is intentionally a separate long-running check
from normal PR verification because marketplace rate limits can make a full
India-wide crawl expensive.
"""
from __future__ import annotations

import concurrent.futures
import json
import sys
import time

from src.live_marketplaces import live_brands, live_models, live_inventory

MAX_WORKERS = 6
MODEL_TIMEOUT = 45


def main() -> int:
    started=time.time()
    brands=live_brands()
    catalog=[]
    catalog_errors=[]
    for b in brands:
        try:
            models=live_models(b["name"])
            catalog.append((b["name"],models))
        except Exception as exc:
            catalog_errors.append({"brand":b["name"],"error":str(exc)[:200]})

    pairs=[(brand,m["name"]) for brand,models in catalog for m in models]
    if not brands:
        print(json.dumps({"status":"error","error":"live brand catalog is empty"}, indent=2))
        return 2
    if not pairs:
        print(json.dumps({"status":"error","error":"live model catalog is empty"}, indent=2))
        return 2
    results=[]
    def probe(pair):
        brand,model=pair
        t=time.time()
        try:
            vehicles,sources=live_inventory(f"{brand} {model}")
            query=f"{brand} {model}".strip()
            matched=[v for v in vehicles if __import__("src.live_marketplaces", fromlist=["_identity_matches_query"])._identity_matches_query(v, query)]
            return {
                "brand":brand,"model":model,"status":"ok",
                "vehicles":len(vehicles),"matched":len(matched),
                "live_sources":sum(s.get("status")=="live" for s in sources),
                "source_failures":sum(s.get("status")=="unavailable" for s in sources),
                "seconds":round(time.time()-t,2),
            }
        except Exception as exc:
            return {"brand":brand,"model":model,"status":"error","error":str(exc)[:240]}

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for r in pool.map(probe,pairs):
            results.append(r)

    zero=[r for r in results if r["status"]=="ok" and r["matched"]==0]
    errors=[r for r in results if r["status"]=="error"]
    # A zero match is a hard failure only when the selected live sources
    # actually reported live inventory. Empty inventory is valid for a model
    # with no current listings; live inventory that fails identity matching is
    # the correctness defect this matrix is intended to catch.
    actionable_zero=[r for r in zero if r["live_sources"] > 0]
    report={
        "generated_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "brands":len(brands),
        "catalog_errors":catalog_errors,
        "models":len(pairs),
        "probes":len(results),
        "zero_match_models":len(zero),
        "actionable_zero_match_models":len(actionable_zero),
        "probe_errors":len(errors),
        "elapsed_seconds":round(time.time()-started,1),
        "zero_matches":zero[:200],
        "actionable_zero_matches":actionable_zero[:200],
        "errors":errors[:200],
        "brand_model_counts":{brand:len(models) for brand,models in catalog},
    }
    print(json.dumps(report,indent=2,ensure_ascii=False))
    # A source outage is not itself a model defect. Fail only on catalog errors
    # or probe errors; zero matches are reported for investigation because some
    # models legitimately have no current used inventory.
    return 1 if catalog_errors or errors or actionable_zero else 0


if __name__=="__main__":
    raise SystemExit(main())
