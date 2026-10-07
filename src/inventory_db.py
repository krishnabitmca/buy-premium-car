from __future__ import annotations

"""Read-only PostgreSQL inventory search path.

The customer result is a canonical vehicle with one or more provider offers.
Only the freshest verified observation for each listing participates.
"""

import os
from datetime import datetime, timezone
from typing import Any

from .source_registry_db import enabled as source_db_enabled, _connect
from .live_marketplaces import _query_parts


def enabled() -> bool:
    return source_db_enabled() and os.getenv("CARSCANNER_INVENTORY_FIRST", "true").lower() not in {"0", "false", "no"}


def search_inventory(
    *,
    query: str = "",
    condition: str = "both",
    budget_min: float | None = None,
    budget_max: float | None = None,
    max_age_years: float | None = None,
    limit: int = 500,
    offset: int = 0,
    return_count: bool = False,
):
    if not enabled():
        return ([], [], 0) if return_count else ([], [])

    brand, model = _query_parts(query)
    condition = str(condition or "both").strip().lower()
    params: list[Any] = []
    predicates = [
        "l.status = 'active'",
        "v.status in ('active','unknown')",
        "o.live_verified = true",
        "o.sold_signal = false",
        "l.last_verified_at >= now() - interval '7 days'",
    ]
    if brand:
        predicates.append("lower(v.brand) = lower(%s)"); params.append(brand)
    if model:
        predicates.append("lower(v.model) = lower(%s)"); params.append(model)
    if condition in {"used", "demo"}:
        predicates.append("v.condition = %s"); params.append(condition)
    if budget_min is not None:
        predicates.append("o.price_lakh >= %s"); params.append(float(budget_min))
    if budget_max is not None:
        predicates.append("o.price_lakh <= %s"); params.append(float(budget_max))
    if max_age_years is not None:
        predicates.append("v.manufacture_year is not null and v.manufacture_year >= %s")
        params.append(datetime.now(timezone.utc).year - int(max_age_years))

    safe_limit=max(1,min(int(limit),2000)); safe_offset=max(0,min(int(offset),1_000_000))
    where=" and ".join(predicates)
    base=f"""
      with latest_listing as (
        select
          v.vehicle_id,v.brand,v.model,v.variant,v.manufacture_year as mfg_year,
          v.registration_year,v.condition,v.fuel,v.transmission,
          v.seller_city as vehicle_location,v.seller_state,v.identity_confidence,
          l.listing_id,l.url,l.final_url,l.title as listing_name,l.seller_name,
          l.seller_city,l.seller_state as listing_seller_state,l.last_verified_at,
          o.price_lakh,o.mileage_km as km,o.owner_count as owners,o.observed_at,
          o.live_verified,o.data_consistent,s.name as source,
          coalesce(l.metadata->'image_urls',v.metadata->'image_urls','[]'::jsonb) as image_urls,
          row_number() over(partition by l.listing_id order by o.observed_at desc) as listing_rn
        from public.vehicle_observations o
        join public.vehicles v on v.vehicle_id=o.vehicle_id
        join public.listings l on l.listing_id=o.listing_id
        join public.sources s on s.source_id=o.source_id
        where {where}
      ), grouped as (
        select
          vehicle_id,brand,model,variant,mfg_year,registration_year,condition,fuel,transmission,
          vehicle_location as location,seller_state,identity_confidence,
          min(price_lakh) as price_lakh,
          (array_agg(km order by price_lakh nulls last))[1] as km,
          (array_agg(owners order by price_lakh nulls last))[1] as owners,
          max(observed_at) as observed_at,
          bool_and(data_consistent) as data_consistent,
          true as live_verified,
          (array_agg(source order by price_lakh nulls last))[1] as source,
          (array_agg(url order by price_lakh nulls last))[1] as url,
          (array_agg(final_url order by price_lakh nulls last))[1] as final_url,
          (array_agg(listing_name order by price_lakh nulls last))[1] as listing_name,
          (array_agg(image_urls order by price_lakh nulls last))[1] as image_urls,
          count(*)::int as source_count,
          jsonb_agg(jsonb_build_object(
            'source',source,'url',url,'final_url',final_url,'price_lakh',price_lakh,
            'seller_name',seller_name,'seller_city',seller_city,
            'seller_state',listing_seller_state,'last_verified_at',last_verified_at
          ) order by price_lakh nulls last, source) as offers
        from latest_listing where listing_rn=1
        group by vehicle_id,brand,model,variant,mfg_year,registration_year,condition,fuel,
                 transmission,vehicle_location,seller_state,identity_confidence
      )
    """
    sql=base+"""select * from grouped order by price_lakh nulls last, observed_at desc limit %s offset %s"""
    count_sql=base+"""select count(*)::bigint as total_count from grouped"""
    with _connect() as conn,conn.cursor() as cur:
        total=None
        if return_count:
            cur.execute(count_sql,params); total=int(cur.fetchone()["total_count"])
        cur.execute(sql,list(params)+[safe_limit,safe_offset]); rows=[dict(r) for r in cur.fetchall()]

    sources=[]; seen=set()
    for row in rows:
        offers=list(row.get("offers") or [])
        # Rolling-migration compatibility: older inventory rows expose only the
        # cheapest/top-level source. Preserve it as a single provider offer so
        # callers always receive the canonical multi-offer contract.
        if not offers and row.get("source"):
            offers=[{
                "source":row.get("source"),
                "url":row.get("url"),
                "final_url":row.get("final_url"),
                "price_lakh":row.get("price_lakh"),
            }]
        row["offers"]=offers
        row["source_listings"]=offers
        row["source_count"]=max(int(row.get("source_count") or 0), len(offers))
        for offer in offers:
            name=offer.get("source")
            if name and name not in seen:
                seen.add(name); sources.append({"name":name,"status":"inventory","mode":"inventory"})
    return (rows,sources,total) if return_count else (rows,sources)
