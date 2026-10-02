from __future__ import annotations

"""Read-only PostgreSQL inventory search path for customer requests.

The inventory tables are populated by background crawlers. Customer traffic
should read this path first and only fall back to live acquisition when the
inventory cannot satisfy the request.
"""

import os
from datetime import datetime, timezone
from typing import Any

from .source_registry_db import database_url, enabled as source_db_enabled, _connect


def enabled() -> bool:
    return source_db_enabled() and os.getenv("CARSCANNER_INVENTORY_FIRST", "true").lower() not in {"0", "false", "no"}


def _query_parts(query: str) -> tuple[str, str]:
    tokens = [t for t in str(query or "").split() if t]
    if not tokens:
        return "", ""
    from .live_marketplaces import CURRENT_BRANDS, BRAND_ALIASES
    lowered = " ".join(tokens).lower()
    brands = sorted(
        list(CURRENT_BRANDS) + list(BRAND_ALIASES.keys()),
        key=lambda x: len(x),
        reverse=True,
    )
    for brand in brands:
        b = brand.lower()
        if lowered.startswith(b):
            model = " ".join(tokens[len(brand.split()):])
            return brand, model
    return tokens[0], " ".join(tokens[1:])


def search_inventory(
    *,
    query: str = "",
    condition: str = "both",
    budget_min: float | None = None,
    budget_max: float | None = None,
    max_age_years: float | None = None,
    limit: int = 500,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return the freshest active observation per vehicle from PostgreSQL."""
    if not enabled():
        return [], []

    brand, model = _query_parts(query)
    condition = str(condition or "both").strip().lower()
    params: list[Any] = []
    predicates = [
        "l.status = 'active'",
        "v.status in ('active','unknown')",
        "o.live_verified = true",
        "o.sold_signal = false",
    ]

    if brand:
        predicates.append("lower(v.brand) = lower(%s)")
        params.append(brand)
    if model:
        predicates.append("lower(v.model) = lower(%s)")
        params.append(model)
    if condition in {"used", "demo"}:
        predicates.append("v.condition = %s")
        params.append(condition)
    if budget_min is not None:
        predicates.append("o.price_lakh >= %s")
        params.append(float(budget_min))
    if budget_max is not None:
        predicates.append("o.price_lakh <= %s")
        params.append(float(budget_max))
    if max_age_years is not None:
        predicates.append("(v.manufacture_year is not null and v.manufacture_year >= %s)")
        params.append(datetime.now(timezone.utc).year - int(max_age_years))

    params.append(max(1, min(int(limit), 2000)))
    where = " and ".join(predicates)

    sql = f"""
      with ranked as (
        select
          v.vehicle_id, v.brand, v.model, v.variant,
          v.manufacture_year as mfg_year, v.registration_year,
          v.condition, v.fuel, v.transmission,
          v.seller_city as location, v.seller_state,
          v.status as vehicle_status, v.identity_confidence,
          l.listing_id, l.url, l.final_url, l.title as listing_name,
          l.seller_name, l.seller_city, l.seller_state,
          o.price_lakh, o.mileage_km as km, o.owner_count as owners,
          o.observed_at, o.live_verified, o.data_consistent,
          o.sold_signal, s.name as source,
          row_number() over (
            partition by v.vehicle_id
            order by o.observed_at desc, l.last_seen_at desc
          ) as rn
        from public.vehicle_observations o
        join public.vehicles v on v.vehicle_id=o.vehicle_id
        left join public.listings l on l.listing_id=o.listing_id
        join public.sources s on s.source_id=o.source_id
        where {where}
      )
      select * from ranked where rn=1
      order by observed_at desc
      limit %s
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

    sources = []
    seen = set()
    for row in rows:
        name = row.get("source")
        if name and name not in seen:
            seen.add(name)
            sources.append({"name": name, "status": "inventory", "mode": "inventory"})
    return rows, sources
