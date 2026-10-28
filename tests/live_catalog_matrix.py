"""Live catalog matrix verification.

Enumerates the live brand/model catalog and probes every model against every
configured live source. This is intentionally a separate long-running check
from normal PR verification because marketplace rate limits can make a full
India-wide crawl expensive.
"""
from __future__ import annotations

import concurrent.futures
import os
import signal
import json
import sys
import time

from src.live_marketplaces import live_brands, live_models, live_inventory

MAX_WORKERS = 4
MODEL_TIMEOUT = 45  # Diagnostic threshold; network calls must enforce their own timeouts.
MAX_MATRIX_SECONDS = int(os.getenv('CARSCANNER_MATRIX_SECONDS', '2100'))


def _actionable_zero_matches(results):
    """Flag zero matches only when returned vehicle cards failed identity matching.

    An available/live source is not evidence of inventory for a specific model.
    A model can legitimately have no currently advertised used/demo vehicles.
    """
    return [
        r for r in results
        if r.get("status") == "ok"
        and r.get("matched") == 0
        and r.get("vehicles", 0) > 0
    ]


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

    all_pairs=[(brand,m["name"]) for brand,models in catalog for m in models]
    shard_count=int(os.getenv("CARSCANNER_MATRIX_SHARDS","1"))
    shard_index=int(os.getenv("CARSCANNER_MATRIX_SHARD","0"))
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        print("Invalid matrix shard configuration",file=sys.stderr)
        return 2
    pairs=[pair for i,pair in enumerate(all_pairs) if i % shard_count == shard_index]
    print(f"Live matrix shard {shard_index+1}/{shard_count}: {len(pairs)}/{len(all_pairs)} models; {MAX_WORKERS} workers",file=sys.stderr,flush=True)
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

    pool=concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
    pending={pool.submit(probe,pair):pair for pair in pairs}
    try:
        while pending:
            remaining=MAX_MATRIX_SECONDS-(time.time()-started)
            if remaining <= 0:
                break
            done,_=concurrent.futures.wait(pending,timeout=min(15,remaining),return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                pair=pending.pop(future)
                try:
                    r=future.result()
                except Exception as exc:
                    r={'brand':pair[0],'model':pair[1],'status':'error','error':str(exc)[:240]}
                results.append(r)
                if r.get('seconds',0) > MODEL_TIMEOUT or r['status']=='error':
                    print(f"Slow/error probe {r['brand']} {r['model']}: {r.get('seconds','?')}s {r['status']}",file=sys.stderr,flush=True)
            print(f"Live matrix progress: {len(results)}/{len(pairs)} models in {time.time()-started:.0f}s",file=sys.stderr,flush=True)
    finally:
        unfinished=list(pending.values())
        for future in pending:
            future.cancel()
        pool.shutdown(wait=False,cancel_futures=True)
    if unfinished:
        print(f"Live matrix budget exhausted: {len(unfinished)} unfinished model probes",file=sys.stderr,flush=True)

    zero=[r for r in results if r["status"]=="ok" and r["matched"]==0]
    errors=[r for r in results if r["status"]=="error"]
    # A source marked "live" means its adapter is available, not that it
    # returned any vehicles for this particular model. Distinguish a genuine
    # identity-matching failure from a legitimate zero-inventory search.
    actionable_zero=_actionable_zero_matches(results)
    report={
        "generated_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "brands":len(brands),
        "shard_index":shard_index,
        "shard_count":shard_count,
        "catalog_total_models":len(all_pairs),
        "catalog_errors":catalog_errors,
        "models":len(pairs),
        "probes":len(results),
        "zero_match_models":len(zero),
        "actionable_zero_match_models":len(actionable_zero),
        "probe_errors":len(errors),
        "unfinished_models":len(unfinished),
        "unfinished_examples":[{"brand":b,"model":model} for b,model in unfinished[:200]],
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
    return 1 if catalog_errors or errors or unfinished else 0


if __name__=="__main__":
    raise SystemExit(main())
