from __future__ import annotations

"""Demand/freshness aware refresh scheduler.

The scheduler creates deduplicated refresh work. It never fetches marketplaces.
Execution remains the responsibility of the source-isolated adapter worker.
"""

import json
from typing import Any
from .inventory_freshness import refresh_priority
from .source_registry_db import _connect, enabled, load_search_demand, require_database


def _reliability(status: Any) -> float:
    value = str(status or "").lower()
    return {"healthy": 1.2, "degraded": 0.8, "unavailable": 0.4, "unhealthy": 0.4, "blocked": 0.2, "unknown": 1.0}.get(value, 1.0)


def schedule_refreshes(*, limit: int = 100, lookback_hours: int = 168) -> int:
    if not enabled():
        return 0

    demands = load_search_demand(limit=limit, lookback_hours=lookback_hours)
    # Always maintain a global India-wide refresh demand. This bootstraps the
    # inventory even before enough customer searches exist and keeps source
    # freshness independent from customer traffic.
    global_demand = {
        "brand": "", "model": "", "condition": "both",
        "destination_state": "", "search_count": 1, "inventory_hit_count": 0,
    }
    demands = [global_demand] + [d for d in demands if not (
        not d.get("brand") and not d.get("model") and str(d.get("condition") or "both") == "both"
    )]
    created = 0

    with _connect() as conn, conn.cursor() as cur:
        for demand in demands:
            brand = str(demand.get("brand") or "")
            model = str(demand.get("model") or "")
            condition = str(demand.get("condition") or "both")
            state = str(demand.get("destination_state") or "")
            search_count = int(demand.get("search_count") or 0)
            hit_count = int(demand.get("inventory_hit_count") or 0)

            cur.execute(
                """select s.source_id, s.name,
                          coalesce(s.freshness_target_minutes,360) as target_minutes,
                          coalesce(s.stale_after_minutes,1440) as stale_after_minutes,
                          coalesce(s.expire_after_minutes,10080) as expire_after_minutes,
                          coalesce(sh.status,'healthy') as health_status,
                          coalesce(
                            extract(epoch from (now()-max(l.last_verified_at)))/60,
                            999999
                          ) as age_minutes
                     from public.sources s
                     join public.source_adapters sa
                       on sa.source_id=s.source_id and sa.status='verified'
                     left join public.source_health sh
                       on sh.source_id=s.source_id
                       and sh.health_id=(
                         select sh2.health_id
                           from public.source_health sh2
                          where sh2.source_id=s.source_id
                          order by sh2.checked_at desc
                          limit 1
                       )
                     left join public.listings l
                       on l.source_id=s.source_id and l.status='active'
                     where s.enabled=true
                       and s.adapter_status='live'
                       and (
                         %s=''
                         or exists (
                           select 1 from public.source_capabilities sc
                            where sc.source_id=s.source_id
                              and sc.capability_type='brand'
                              and lower(sc.capability_value) in (lower(%s),'all')
                         )
                       )
                     group by s.source_id,s.name,s.freshness_target_minutes,
                              s.stale_after_minutes,s.expire_after_minutes,sh.status""",
                (brand, brand),
            )
            sources = cur.fetchall()

            for source in sources:
                age = float(source.get("age_minutes") or 999999)
                if age <= float(source.get("target_minutes") or 360):
                    continue

                freshness = (
                    "expired" if age > float(source.get("expire_after_minutes") or 10080)
                    else "stale" if age > float(source.get("stale_after_minutes") or 1440)
                    else "aging"
                )
                priority = refresh_priority(
                    search_count=search_count,
                    inventory_hit_count=hit_count,
                    freshness=freshness,
                    source_reliability=_reliability(source.get("health_status")),
                )
                reason = "demand_gap" if search_count > hit_count else freshness

                cur.execute(
                    """insert into public.inventory_refresh_queue
                       (source_id,brand,model,condition,destination_state,
                        priority,reason,status,metadata)
                       values (%s,%s,%s,%s,%s,%s,%s,'queued',%s)
                       on conflict (source_id,brand,model,condition,destination_state)
                       do update set
                         priority=greatest(public.inventory_refresh_queue.priority,
                                           excluded.priority),
                         reason=excluded.reason,
                         requested_at=now(),
                         status=case
                           when public.inventory_refresh_queue.status in ('completed','failed')
                           then 'queued'
                           else public.inventory_refresh_queue.status
                         end,
                         metadata=excluded.metadata""",
                    (
                        source["source_id"], brand, model, condition, state,
                        priority, reason,
                        json.dumps({"search_count": search_count, "inventory_hit_count": hit_count,
                                    "freshness": freshness, "source_health": source.get("health_status")}),
                    ),
                )
                created += 1

        conn.commit()

    return created


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--lookback-hours", type=int, default=168)
    args = parser.parse_args()
    require_database()
    print(schedule_refreshes(limit=args.limit, lookback_hours=args.lookback_hours))


if __name__ == "__main__":
    main()
