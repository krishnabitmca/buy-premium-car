from __future__ import annotations

"""Demand/freshness aware refresh scheduler.

The scheduler creates deduplicated refresh work. It never fetches marketplaces.
Execution remains the responsibility of the source-isolated adapter worker.
"""

import json
from typing import Any
from .inventory_freshness import refresh_priority
from .car_catalog import CAR_MAKES
from .source_registry_db import _connect, enabled, load_search_demand, require_database, load_registry


def baseline_brand_demands():
    """Warm every supported make, independently of customer traffic.

    Registry capabilities supplement the independent make taxonomy. An ``all``
    capability means multi-brand coverage; it is never itself a brand job.
    Sources without verified adapters remain excluded by the scheduling SQL.
    """
    brands = {brand.lower():brand for brand in CAR_MAKES}
    for source in load_registry():
        for value in source.get('brands') or []:
            brand = str(value or '').strip()
            if brand and brand.lower() not in {'all', '*'}:
                brands.setdefault(brand.lower(), brand)
    return [dict(brand=brand, model='', condition='both', destination_state='',
                 search_count=1, inventory_hit_count=1)
            for _, brand in sorted(brands.items())]


def _reliability(status: Any) -> float:
    value = str(status or "").lower()
    return {"healthy": 1.2, "degraded": 0.8, "unavailable": 0.4, "unhealthy": 0.4, "blocked": 0.2, "unknown": 1.0}.get(value, 1.0)


def schedule_refreshes(*, limit: int = 100, lookback_hours: int = 168) -> int:
    if not enabled():
        return 0

    from .used_inventory_frontier import reschedule_models
    reschedule_models()
    from .catalog_traversal import wake_catalogues
    wake_catalogues()

    demands = load_search_demand(limit=limit, lookback_hours=lookback_hours)
    # Always maintain a global India-wide refresh demand. This bootstraps the
    # inventory even before enough customer searches exist and keeps source
    # freshness independent from customer traffic.
    global_demand = {
        "brand": "", "model": "", "condition": "both",
        "destination_state": "", "search_count": 1, "inventory_hit_count": 0,
    }
    # Customer demand comes first so its priority is retained when it overlaps
    # a baseline job. Brand scans remain India-wide regardless of destination.
    unique_demands = {}
    for demand in [global_demand,{**global_demand,'condition':'demo'}] + demands + baseline_brand_demands():
        key = tuple(str(demand.get(k) or ('both' if k == 'condition' else '')).strip().lower()
                    for k in ('brand', 'model', 'condition', 'destination_state'))
        unique_demands.setdefault(key, demand)
    demands = list(unique_demands.values())
    created = 0

    with _connect() as conn, conn.cursor() as cur:
        for demand in demands:
            brand = str(demand.get("brand") or "").strip().lower()
            model = str(demand.get("model") or "").strip().lower()
            condition = str(demand.get("condition") or "both").strip().lower()
            state = str(demand.get("destination_state") or "").strip().lower()
            search_count = int(demand.get("search_count") or 0)
            hit_count = int(demand.get("inventory_hit_count") or 0)

            cur.execute(
                """select s.source_id, s.name,
                          coalesce(s.freshness_target_minutes,360) as target_minutes,
                          coalesce(s.stale_after_minutes,1440) as stale_after_minutes,
                          coalesce(s.expire_after_minutes,10080) as expire_after_minutes,
                          coalesce(sh.status,'healthy') as health_status,
                          coalesce(
                            extract(epoch from (now()-(q.metadata->>'last_success_at')::timestamptz))/60,
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
                     left join public.inventory_refresh_queue q
                       on q.source_id=s.source_id and q.brand=%s and q.model=%s
                       and q.condition=%s and q.destination_state=%s
                     where s.enabled=true
                       and s.adapter_status='live'
                       and (%s<>'demo' or %s<>'' or %s<>'' or exists (
                         select 1 from source_capabilities dc where dc.source_id=s.source_id
                           and dc.capability_type='condition' and lower(dc.capability_value)='demo'))
                       and (
                         %s=''
                         or exists (
                           select 1 from public.source_capabilities sc
                            where sc.source_id=s.source_id
                              and sc.capability_type='brand'
                              and lower(sc.capability_value) in (lower(%s),'all')
                         )
                       )
                       and (s.metadata->>'global_catalogue_only' is distinct from 'true'
                            or (%s='' and %s='' and %s='' and %s='both'))
                     group by s.source_id,s.name,s.freshness_target_minutes,
                              s.stale_after_minutes,s.expire_after_minutes,sh.status,q.metadata""",
                (brand, model, condition, state,condition,brand,model,brand,brand,brand,model,state,condition),
            )
            sources = cur.fetchall()

            for source in sources:
                age_value = source.get("age_minutes")
                age = 999999 if age_value is None else float(age_value)
                target=min(float(source.get("target_minutes") or 360),180 if condition=='demo' else 360)
                if age <= target:
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
                         requested_at=case when public.inventory_refresh_queue.status='completed'
                           then now() else public.inventory_refresh_queue.requested_at end,
                         status=case
                           when public.inventory_refresh_queue.status='completed'
                           then 'queued'
                           else public.inventory_refresh_queue.status
                         end,
                         attempt_count=case when public.inventory_refresh_queue.status='completed'
                                            then 0 else public.inventory_refresh_queue.attempt_count end,
                         metadata=(case when public.inventory_refresh_queue.status='completed'
                           then public.inventory_refresh_queue.metadata - 'retry_base' - 'pages_fetched'
                           else public.inventory_refresh_queue.metadata end) || excluded.metadata""",
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
    parser.add_argument('--seed-observed-models',action='store_true',help='Learn used/discontinued model families from source observations')
    args = parser.parse_args()
    require_database()
    if args.seed_observed_models:
        from .used_inventory_frontier import seed_observed_models
        print({'model_jobs_seeded':seed_observed_models()})
    print(schedule_refreshes(limit=args.limit, lookback_hours=args.lookback_hours))


if __name__ == "__main__":
    main()
