from __future__ import annotations

"""Background refresh worker.

Execute verified source adapters with their complete database configuration.
Queue claims are source-isolated and retries are bounded.
"""

import argparse
import logging
from typing import Any

from .inventory_ingestion import ingest_vehicles
from .source_adapters import AdapterRequest, BuiltinMarketplaceAdapter
from .source_registry_db import _connect, enabled, require_database, load_registry

log = logging.getLogger(__name__)


def claim_jobs(limit: int = 10) -> list[dict[str, Any]]:
    if not enabled():
        return []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """with picked as (
                 select q.refresh_id
                 from public.inventory_refresh_queue q
                 join public.sources s on s.source_id=q.source_id
                 where q.status='queued'
                   and s.enabled=true
                   and s.adapter_status='live'
                   and exists (
                     select 1 from public.source_adapters sa
                     where sa.source_id=s.source_id and sa.status='verified'
                   )
                 order by q.priority desc, q.requested_at asc
                 for update of q skip locked
                 limit %s
               )
               update public.inventory_refresh_queue q
               set status='running',started_at=now(),attempt_count=attempt_count+1
               from picked where q.refresh_id=picked.refresh_id
               returning q.*, (select s.name from public.sources s where s.source_id=q.source_id) as source_name,\n                       (select s.url from public.sources s where s.source_id=q.source_id) as source_url""",
            (max(1, min(int(limit), 100)),),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
    return rows


def recover_jobs() -> int:
    """Retry failures with backoff and recover abandoned 30-minute claims.

    Three attempts exhaust a job. Operators explicitly reset exhausted work
    after inspecting the source; the scheduler cannot retry it indefinitely.
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""update public.inventory_refresh_queue
            set status=case when attempt_count < 3 then 'queued' else 'failed' end,
                completed_at=now(),
                last_error=case when status='running' then 'worker claim expired'
                                else last_error end
            where (status='running' and started_at < now()-interval '30 minutes')
               or (status='failed' and attempt_count < 3
                   and completed_at < now()-make_interval(mins => 5 * power(2, attempt_count)::int))""")
        recovered = cur.rowcount
        conn.commit()
        return recovered


def complete_job(refresh_id: int, *, success: bool, error: str | None = None,
                 attempt_count: int | None = None) -> None:
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """update public.inventory_refresh_queue
               set status=%s,completed_at=now(),last_error=%s,
                   metadata=case when %s then metadata ||
                       jsonb_build_object('last_success_at',now()) else metadata end
               where refresh_id=%s and status='running'
                 and (%s::integer is null or attempt_count=%s)""",
            ("completed" if success else "failed", error, success, refresh_id,
             attempt_count, attempt_count),
        )
        conn.commit()


def process_job(job: dict[str, Any]) -> dict[str, int]:
    query = " ".join(x for x in (job.get("brand"), job.get("model")) if x)
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
        adapter = BuiltinMarketplaceAdapter(source)
        result = adapter.fetch(
            AdapterRequest(
                query=query,
                condition=job.get("condition") or "both",
                destination=job.get("destination_state") or "",
            )
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

        ingested = ingest_vehicles(normalized)
        complete_job(int(job["refresh_id"]), success=True, attempt_count=job.get("attempt_count"))
        return ingested
    except Exception as exc:
        complete_job(int(job["refresh_id"]), success=False, error=str(exc)[:1000],
                     attempt_count=job.get("attempt_count"))
        raise


def run_batch(limit: int = 10) -> dict[str, int]:
    """Claim only when ready to execute; isolate marketplace failures."""
    counts = {"completed": 0, "failed": 0}
    recover_jobs()
    for _ in range(max(1, min(int(limit), 100))):
        jobs = claim_jobs(1)
        if not jobs:
            break
        try:
            process_job(jobs[0])
            counts["completed"] += 1
        except Exception:
            counts["failed"] += 1
            log.exception("Refresh failed for job %s", jobs[0]["refresh_id"])
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    require_database()
    logging.basicConfig(level=logging.INFO)
    result = run_batch(args.limit)
    print(result)
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
