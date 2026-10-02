from __future__ import annotations

"""Background refresh worker.

The current adapter bridge reuses the existing live acquisition path and filters
the result to the requested source. This is intentionally transitional; the
next adapter version should expose a source-isolated fetch() primitive.
"""

import argparse
from typing import Any

from .inventory_ingestion import ingest_vehicles
from .source_adapters import AdapterRequest, BuiltinMarketplaceAdapter
from .source_registry_db import _connect, enabled


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
               returning q.*, (select s.name from public.sources s where s.source_id=q.source_id) as source_name""",
            (max(1, min(int(limit), 100)),),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
    return rows


def complete_job(refresh_id: int, *, success: bool, error: str | None = None) -> None:
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """update public.inventory_refresh_queue
               set status=%s,completed_at=now(),last_error=%s
               where refresh_id=%s""",
            ("completed" if success else "failed", error, refresh_id),
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
        source = {
            "name": source_name,
            "adapter_status": "live",
            "url": str(job.get("metadata", {}).get("source_url") or ""),
        }
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
            seller_state=v.get("seller_state"), condition_signal=v.get("condition_signal"),
            final_url=v.get("final_url"), live_verified=bool(v.get("live_verified")),
            sold_signal=bool(v.get("sold_signal")), data_consistent=bool(v.get("data_consistent", True)),
            identity_confidence=float(v.get("identity_confidence") or 0.0),
        ) for v in result.listings]

        ingested = ingest_vehicles(normalized)
        complete_job(int(job["refresh_id"]), success=True)
        return ingested
    except Exception as exc:
        complete_job(int(job["refresh_id"]), success=False, error=str(exc)[:1000])
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    for job in claim_jobs(args.limit):
        process_job(job)


if __name__ == "__main__":
    main()
