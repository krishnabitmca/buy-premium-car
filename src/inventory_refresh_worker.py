from __future__ import annotations

"""Background refresh worker.

Execute verified source adapters with their complete database configuration.
Queue claims are source-isolated and retries are bounded.
"""

import argparse
import logging
import json
import os
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import Any

from .inventory_ingestion import ingest_vehicles
from .source_adapters import AdapterRequest, BuiltinMarketplaceAdapter
from .source_registry_db import _connect, enabled, require_database, load_registry

log = logging.getLogger(__name__)


def claim_jobs(limit: int = 10, *, brands=None, source_names=None, baseline_only=False, models_only=False, continuations_only=False, catalogues_only=False, demo_only=False) -> list[dict[str, Any]]:
    if not enabled():
        return []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """with brand_service as (
                 select lower(brand) as brand,max(started_at) as last_started
                 from public.inventory_refresh_queue group by lower(brand)
               ), picked as (
                 select q.refresh_id
                 from public.inventory_refresh_queue q
                 join public.sources s on s.source_id=q.source_id
                 join brand_service b on b.brand=lower(q.brand)
                 where q.status='queued'
                   and coalesce((q.metadata->>'next_attempt_at')::timestamptz,'epoch')<=now()
                   and not exists(select 1 from inventory_crawl_leases d
                     where d.domain=substring(lower(s.url) from '^https?://([^/:]+)')
                       and (d.lease_expires_at>now() or d.next_allowed_at>now()))
                   and (not %s or (q.brand='' and q.model='' and q.destination_state='' and q.condition='demo'
                     and exists(select 1 from source_capabilities sc where sc.source_id=s.source_id
                         and sc.capability_type='condition' and lower(sc.capability_value)='demo')))
                   and (not %s or (q.brand='' and q.model='' and q.destination_state='' and q.condition='both'
                     and (s.metadata ? 'city_catalog_path_pattern' or s.metadata ? 'catalogue_link_pattern')))
                   and (not %s or (q.model<>'' and q.metadata ? 'model_discovery'))
                   and (not %s or q.metadata ? 'continuation')
                   and (not %s or (q.brand<>'' and q.model='' and q.condition='both' and q.destination_state=''))
                   and (%s::text[] is null or lower(q.brand)=any(%s::text[]))
                   and (%s::text[] is null or s.name=any(%s::text[]))
                   and s.enabled=true
                   and s.adapter_status='live'
                   and exists (
                     select 1 from public.source_adapters sa
                     where sa.source_id=s.source_id and sa.status='verified'
                   )
                 order by b.last_started asc nulls first,
                          q.started_at asc nulls first,q.priority desc,q.requested_at asc,q.refresh_id
                 for update of q skip locked
                 limit %s
               )
               update public.inventory_refresh_queue q
               set status='running',started_at=now(),attempt_count=attempt_count+1
               from picked where q.refresh_id=picked.refresh_id
               returning q.*, (select s.name from public.sources s where s.source_id=q.source_id) as source_name,\n                       (select s.url from public.sources s where s.source_id=q.source_id) as source_url""",
            (bool(demo_only),bool(catalogues_only),bool(models_only),bool(continuations_only),bool(baseline_only)) + ([str(b).strip().lower() for b in brands] if brands else None,)*2 +
            (list(source_names) if source_names else None,)*2 + (max(1,min(int(limit),100)),),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
    return rows


def recover_jobs() -> int:
    """Retry failures with backoff and recover abandoned 30-minute claims.

    Three failures since the last successful batch exhaust a job.
    Operators explicitly reset exhausted work
    after inspecting the source; the scheduler cannot retry it indefinitely.
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""update public.inventory_refresh_queue
            set status=case when attempt_count - coalesce((metadata->>'retry_base')::integer,0) < 3 then 'queued' else 'failed' end,
                completed_at=now(),
                last_error=case when status='running' then 'worker claim expired'
                                else last_error end
            where (status='running' and started_at < now()-interval '30 minutes')
               or (status='failed' and attempt_count - coalesce((metadata->>'retry_base')::integer,0) < 3
                   and completed_at < now()-make_interval(mins => 5 * power(2, attempt_count - coalesce((metadata->>'retry_base')::integer,0))::int))""")
        recovered = cur.rowcount
        conn.commit()
        return recovered


def complete_job(refresh_id: int, *, success: bool, error: str | None = None,
                 attempt_count: int | None = None,
                 continuation: dict[str, Any] | None = None, pages_fetched: int = 0, scan_evidence=None,_connection=None) -> None:
    if not enabled():
        return
    with (nullcontext(_connection) if _connection is not None else _connect()) as conn, conn.cursor() as cur:
        cur.execute(
            """update public.inventory_refresh_queue
               set status=%s,completed_at=now(),last_error=%s,
                   requested_at=case when %s then now() else requested_at end,
                   metadata=case when %s then
                     (metadata - 'continuation') || %s::jsonb ||
                     jsonb_build_object('retry_base',attempt_count) ||
                     jsonb_build_object('pages_fetched',
                       coalesce((metadata->>'pages_fetched')::integer,0)+%s)
                     else metadata end
               where refresh_id=%s and status='running'
                 and (%s::integer is null or attempt_count=%s)""",
            ("queued" if success and continuation else "completed" if success else "failed",
             error, bool(success and continuation), success,
             json.dumps(({"continuation": continuation} if continuation else
                        {"last_success_at": datetime.now(timezone.utc).isoformat()}) |
                        ({'last_scan_evidence':scan_evidence,
                          'last_batch_observed_at':datetime.now(timezone.utc).isoformat()} if scan_evidence else {})),
             max(0, int(pages_fetched)), refresh_id, attempt_count, attempt_count),
        )
        if _connection is None:conn.commit()


def process_job(job: dict[str, Any], *, _capture=None) -> dict[str, int]:
    from .live_marketplaces import _query_parts
    brand=job.get('brand') or ''
    query_brand=_query_parts(brand)[0] or brand
    query = " ".join(x for x in (query_brand, job.get("model")) if x)
    from . import crawl_leases
    lease=None
    try:
        source_name = str(job.get("source_name") or "")
        if not source_name:
            raise ValueError("refresh job has no source_name")

        # Refresh workers execute exactly one verified adapter. They never call
        # the aggregate customer-search path, preventing cross-source crawling.
        # Parser strategy, query templates, tier and active endpoints are part
        # of the adapter contract; rebuilding only name/URL loses that contract.
        source = next((s for s in load_registry()
                       if s.get("source_id") == job.get("source_id")), None)
        if source is None or source.get("adapter_status") != "live":
            raise ValueError("refresh source is no longer enabled and live")
        lease=crawl_leases.acquire(source['url'])
        if lease is None:
            with _connect() as conn:
                conn.execute("""update inventory_refresh_queue set status='queued',attempt_count=attempt_count-1,
                    metadata=metadata || jsonb_build_object('next_attempt_at',(now()+interval '1 minute')::text)
                    where refresh_id=%s and status='running' and attempt_count=%s""",(job['refresh_id'],job['attempt_count']))
                conn.commit()
            return {'deferred':1}
        adapter = BuiltinMarketplaceAdapter(source)
        result = adapter.fetch(
            AdapterRequest(
                query=query,
                condition=job.get("condition") or "both",
                destination=job.get("destination_state") or "",
                continuation=(job.get("metadata") or {}).get("continuation") or {},
            ), **({'_capture':_capture} if _capture is not None else {})
        )
        if result.status != "live":
            raise RuntimeError(result.error or f"adapter status: {result.status}")

        from .models import Vehicle
        normalized = [Vehicle(
            source_name=str(v.get("source") or source_name),
            source_tier=int(v.get("source_tier") or 1),
            url=str(v.get("url") or ""),
            title=str(v.get("listing_name") or v.get("title") or ""),
            brand=v.get("brand"), model=v.get("model"), variant=v.get("variant"),
            year_manufacture=v.get("mfg_year"), year_registration=v.get("registration_year"),
            mileage_km=v.get("km"), owner_count=v.get("owners"), price_lakh=v.get("price_lakh"),
            fuel=v.get("fuel"), transmission=v.get("transmission"),
            body_type=v.get('body_type'),
            location=v.get("location"), seller_city=v.get("seller_city"),
            seller_state=v.get("seller_state"), registration_state=v.get("registration_state"),
            vin=v.get("vin") or v.get("vehicle_identification_number"),
            chassis_number=v.get("chassis_number"), metadata=dict(v.get("metadata") or {}),
            condition_signal=v.get("condition_signal"),
            source_listing_id=v.get("source_listing_id"), price_basis=v.get("price_basis"),
            final_url=v.get("final_url"), live_verified=bool(v.get("live_verified")),
            sold_signal=bool(v.get("sold_signal")), data_consistent=bool(v.get("data_consistent", True)),
            identity_confidence=float(v.get("identity_confidence") or 0.0),
            image_urls=list(v.get("images") or ([v.get("image")] if v.get("image") else [])),
        ) for v in result.listings]

        if result.discovered_models:
            from .used_inventory_frontier import enqueue_models
            brand=job.get('brand') or ''
            enqueue_models(brand,result.discovered_models)
        # Fence all canonical writes, not only queue completion, after network I/O.
        with _connect() as conn,conn.cursor() as cur:
            cur.execute("""select refresh_id from inventory_refresh_queue where refresh_id=%s
                and status='running' and attempt_count=%s and started_at=%s for update""",
                (job['refresh_id'],job['attempt_count'],job['started_at']))
            if not cur.fetchone():return {'superseded':1}
            ledger_batch=None
            accepted=None
            if os.getenv('CARSCANNER_SCAN_LEDGER_ENABLED','false').lower()=='true':
                from .scan_ledger import prepare_batch
                ledger_batch=prepare_batch(job,source['source_id'],result.scan_evidence,conn)
                if ledger_batch['already_committed']:
                    return {'superseded':1}
                accepted=[]
            kwargs={} if accepted is None else {'_accepted_observations':accepted}
            ingested=ingest_vehicles(normalized,_connection=conn,**kwargs)
            if result.tombstones:
                from .inventory_lifecycle import retire_catalogue_evidence
                ingested['retired']=retire_catalogue_evidence(result.tombstones,source_name,job['started_at'],conn,**kwargs)
            if ledger_batch is not None:
                from .scan_ledger import finish_batch
                finish_batch(ledger_batch,accepted,result.scan_evidence,result.continuation,conn)
            complete_job(int(job["refresh_id"]), success=True, attempt_count=job.get("attempt_count"),
                continuation=result.continuation,pages_fetched=result.pages_fetched,scan_evidence=result.scan_evidence,_connection=conn)
            conn.commit()
        return {**ingested, 'pages_fetched': result.pages_fetched,
                'listings_extracted': len(result.listings),
                'listings_unpersisted': max(0, len(result.listings) - ingested.get('listings', 0)),
                'traversals_pending': int(bool(result.continuation))}
    except Exception as exc:
        complete_job(int(job["refresh_id"]), success=False, error=str(exc)[:1000],
                     attempt_count=job.get("attempt_count"))
        raise
    finally:crawl_leases.release(lease)


def run_batch(limit: int = 10, *, brands=None, source_names=None, baseline_only=False, models_only=False, continuations_only=False, catalogues_only=False, demo_only=False, workers: int = 1) -> dict[str, int]:
    """Bounded parallel work; claims are transactional and leases isolate domains.

    Each worker claims only when ready, avoiding 30-minute abandoned claims
    for jobs waiting behind slow network requests.
    """
    from concurrent.futures import ThreadPoolExecutor

    counts = {"completed": 0, "failed": 0}
    recover_jobs()
    total = max(1, min(int(limit), 100))
    parallelism = max(1, min(int(workers), 4, total))
    from threading import Lock
    lock = Lock()
    remaining = total

    def run_one_lane():
        nonlocal remaining
        local = {"completed": 0, "failed": 0}
        while True:
            with lock:
                if remaining <= 0:
                    break
                remaining -= 1
            jobs = claim_jobs(1, brands=brands, source_names=source_names,
                baseline_only=baseline_only, models_only=models_only,
                continuations_only=continuations_only, catalogues_only=catalogues_only,
                demo_only=demo_only)
            if not jobs:
                break
            try:
                result = process_job(jobs[0])
                key = 'deferred' if result.get('deferred') else 'superseded' if result.get('superseded') else 'completed'
                local[key] = local.get(key, 0) + 1
                if key == 'completed':
                    for metric in ('pages_fetched', 'listings_extracted', 'listings_unpersisted', 'traversals_pending'):
                        local[metric] = local.get(metric, 0) + result.get(metric, 0)
            except Exception:
                local['failed'] += 1
                log.exception("Refresh failed for job %s", jobs[0]['refresh_id'])
        return local

    with ThreadPoolExecutor(max_workers=parallelism, thread_name_prefix='inventory-refresh') as pool:
        for lane in pool.map(lambda _: run_one_lane(), range(parallelism)):
            for key, value in lane.items():
                counts[key] = counts.get(key, 0) + value
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--workers", type=int, default=1, help="Parallel source lanes (max 4); domain leases still apply")
    parser.add_argument('--brand',action='append',help='Limit recovery work to this make; repeatable')
    parser.add_argument('--source',action='append',help='Limit recovery to verified source names; repeatable')
    parser.add_argument('--baseline-only',action='store_true',help='Process India-wide make scans, excluding model/location demand jobs')
    parser.add_argument('--models-only',action='store_true',help='Reserve capacity for source-discovered model scans')
    parser.add_argument('--continuations-only',action='store_true',help='Reserve capacity for pending pagination')
    parser.add_argument('--demo-only',action='store_true',help='Reserve global catalogue acquisition for verified demo-capable sources')
    parser.add_argument('--catalogues-only',action='store_true',help='Process reviewed global city/dealer catalogue traversals')
    args = parser.parse_args()
    require_database()
    logging.basicConfig(level=logging.INFO)
    result = run_batch(args.limit,brands=args.brand,source_names=args.source,baseline_only=args.baseline_only,
        models_only=args.models_only,continuations_only=args.continuations_only,catalogues_only=args.catalogues_only,demo_only=args.demo_only,workers=args.workers)
    print(result)
    if result["failed"] and not result["completed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
