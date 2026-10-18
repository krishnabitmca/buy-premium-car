from __future__ import annotations

"""Read-only PostgreSQL inventory search path.

The customer result is a canonical vehicle with one or more provider offers.
Select the actual latest observation before applying price/availability filters.
"""

import os
import time
from contextlib import nullcontext
from .search_timing import measure_call, record_duration
from datetime import datetime, timezone
from typing import Any

from .source_registry_db import enabled as source_db_enabled, _connect, require_database
from .live_marketplaces import _query_parts, _identity_tokens, _canonical_brand, BRAND_ALIASES
from .inventory_contract import json_inventory_value


def enabled() -> bool:
    return source_db_enabled() and os.getenv("CARSCANNER_INVENTORY_FIRST", "true").lower() not in {"0", "false", "no"}


def eligibility_checks():
    """Named canonical checks; diagnostics and search use identical rules."""
    from .inventory_freshness import expiry_sql
    return {
        'listing_inactive': "l.status = 'active'",
        'vehicle_inactive': "v.status in ('active','unknown')",
        'observation_unverified_or_missing': "o.live_verified = true",
        'sold_or_availability_unknown': "o.sold_signal = false",
        'price_invalid_or_missing': "o.price_lakh > 0",
        'source_disabled': "s.enabled = true",
        'adapter_not_live': "s.adapter_status = 'live'",
        'verification_expired_or_missing': "l.last_verified_at >= now() - make_interval(mins => "+expiry_sql()+")",
    }


def eligibility_predicates():
    """Shared offer eligibility for customer search and operational coverage."""
    return list(eligibility_checks().values())


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
    with_summary: bool = False,
    require_persistence: bool = False,
    explain: bool = False,
    fuels=(),
    transmissions=(),
    body_types=(),
    max_mileage_km=None,
    max_owners=None,
    manufacture_year=None,
    seller_city='',
    sort='price',
    _connection=None,
    _vehicle_ids=None,
):
    if require_persistence:
        require_database()
    elif not enabled():
        return ([], [], 0, {}) if with_summary else (([], [], 0) if return_count else ([], []))

    brand, model = _query_parts(query)
    condition = str(condition or "both").strip().lower()
    expire_minutes=max(60, int(os.getenv("CARSCANNER_INVENTORY_EXPIRE_MINUTES", "10080")))
    params: list[Any] = [expire_minutes,expire_minutes]
    predicates = eligibility_predicates()
    if brand:
        canonical=_canonical_brand(brand)
        aliases={brand.lower(),canonical.lower()}
        aliases.update(name.lower() for name,value in BRAND_ALIASES.items() if value.lower()==canonical.lower())
        if len(aliases)>1:
            predicates.append("lower(v.brand) = any(%s)"); params.append(sorted(aliases))
        else:
            predicates.append("lower(v.brand) = lower(%s)"); params.append(brand)
    if model:
        # Dealer model fields often include the trim. Match complete identity
        # tokens, as live adapters do: X5 matches X5 xDrive40i, never X50.
        model_tokens=_identity_tokens(model)
        if model_tokens:
            pattern='(^| )'+' '.join(model_tokens)+'($| )'
            predicates.append("""(regexp_replace(lower(v.model),'[^a-z0-9]+',' ','g') ~ %s
                or regexp_replace(lower(v.variant),'[^a-z0-9]+',' ','g') ~ %s
                or regexp_replace(lower(l.title),'[^a-z0-9]+',' ','g') ~ %s)""")
            params.extend([pattern]*3)
    if condition in {"used", "demo"}:
        predicates.append("v.condition = %s"); params.append(condition)
    baseline_where=' and '.join(predicates)
    predicates=[]
    if budget_min is not None:
        predicates.append("price_lakh >= %s"); params.append(float(budget_min))
    if budget_max is not None:
        predicates.append("price_lakh <= %s"); params.append(float(budget_max))
    if max_age_years is not None:
        predicates.append("mfg_year is not null and mfg_year >= %s")
        params.append(datetime.now(timezone.utc).year - int(max_age_years))

    # These predicates operate on the actual latest source observation, before
    # grouping, totals and pagination. Missing constrained evidence fails closed.
    for values, expression in (
        (fuels, "lower(trim(fuel))"),
        (transmissions, "case when lower(trim(transmission)) in ('automatic','auto','at','dct','cvt','amt','dsg','tiptronic') then 'automatic' when lower(trim(transmission)) in ('manual','mt') then 'manual' else null end"),
        (body_types, "lower(trim(body_type))"),
    ):
        if values:
            predicates.append(expression + ' = any(%s::text[])'); params.append(list(values))
    for value, expression in ((max_mileage_km, 'km <= %s'),
                              (max_owners, 'owners <= %s'),
                              (manufacture_year, 'mfg_year = %s')):
        if value is not None:
            predicates.append(expression); params.append(value)
    if seller_city:
        predicates.append('lower(trim(coalesce(seller_city,vehicle_location))) = lower(%s)')
        params.append(seller_city)
    if sort not in {'price', 'match', 'gap', 'km', 'year'}:
        raise ValueError('Unsupported sort')

    safe_limit=max(1,min(int(limit),2000)); safe_offset=max(0,min(int(offset),1_000_000))
    where=' and '.join(predicates) or 'true'
    # Buyer constraints select eligible offers, but must not redefine the market
    # comparison cohort. Build reference prices from the broader query cohort.
    base=f"""
      with latest_listing as (
        select
          v.vehicle_id,v.brand,v.model,v.variant,v.manufacture_year as mfg_year,
          v.registration_year,v.condition,v.condition as condition_signal,v.fuel,v.transmission,
          v.seller_city as vehicle_location,v.seller_state,v.identity_confidence,
          l.listing_id,l.url,l.final_url,l.title as listing_name,l.seller_name,
          l.seller_city,l.seller_state as listing_seller_state,l.last_verified_at,
          o.price_lakh,o.mileage_km as km,o.owner_count as owners,o.observed_at,
          o.live_verified,o.data_consistent,s.name as source,s.tier as source_tier,
          coalesce(o.snapshot->>'price_basis','unspecified') as price_basis,
          coalesce(o.snapshot->>'body_type',v.metadata->>'body_type') as body_type,
          coalesce(l.metadata->'image_urls',v.metadata->'image_urls','[]'::jsonb) as image_urls
        from public.listings l
        join lateral (
          select observation.* from public.vehicle_observations observation
          where observation.listing_id=l.listing_id
          order by observation.observed_at desc, observation.observation_id desc
          limit 1
        ) o on true
        join public.vehicles v on v.vehicle_id=l.vehicle_id and v.vehicle_id=o.vehicle_id
        join public.sources s on s.source_id=o.source_id
        where {baseline_where}
      ), eligible_listing as (
        select * from latest_listing where {where}
      ), grouped as (
        select
          vehicle_id,brand,model,variant,mfg_year,registration_year,condition,condition_signal,fuel,transmission,body_type,
          vehicle_location as location,seller_state,identity_confidence,price_basis,
          min(price_lakh) as price_lakh,
          (array_agg(km order by price_lakh nulls last,listing_id))[1] as km,
          (array_agg(owners order by price_lakh nulls last,listing_id))[1] as owners,
          (array_agg(observed_at order by price_lakh nulls last,listing_id))[1] as observed_at,
          (array_agg(last_verified_at order by price_lakh nulls last,listing_id))[1] as last_verified_at,
          bool_and(data_consistent) as data_consistent,
          true as live_verified,
          (array_agg(source order by price_lakh nulls last,listing_id))[1] as source,
          (array_agg(source_tier order by price_lakh nulls last,listing_id))[1] as source_tier,
          (array_agg(listing_id order by price_lakh nulls last,listing_id))[1] as listing_id,
          (array_agg(url order by price_lakh nulls last,listing_id))[1] as url,
          (array_agg(final_url order by price_lakh nulls last,listing_id))[1] as final_url,
          (array_agg(listing_name order by price_lakh nulls last,listing_id))[1] as listing_name,
          (array_agg(image_urls order by price_lakh nulls last,listing_id))[1] as image_urls,
          count(distinct source)::int as source_count,
          jsonb_agg(jsonb_build_object(
            'source',source,'source_tier',source_tier,'listing_id',listing_id,
            'url',url,'final_url',final_url,'price_lakh',price_lakh,'price_basis',price_basis,
            'seller_name',seller_name,'seller_city',seller_city,
            'seller_state',listing_seller_state,'last_verified_at',last_verified_at,
            'observed_at',observed_at
          ) order by price_lakh nulls last, source) as offers
        from eligible_listing
        group by vehicle_id,brand,model,variant,mfg_year,registration_year,condition,condition_signal,fuel,
                 transmission,body_type,vehicle_location,seller_state,identity_confidence,price_basis
      ), baseline as (
        select vehicle_id,brand,model,variant,mfg_year,condition,price_basis,
               min(price_lakh) as price_lakh,bool_and(data_consistent) as data_consistent
        from latest_listing
        group by vehicle_id,brand,model,variant,mfg_year,condition,price_basis
      ), cohorts as materialized (
        select brand,model,variant,mfg_year,condition,price_basis,
               (count(*) filter (where data_consistent))::int as comparable_count,
               case when count(*) filter (where data_consistent) >= 3
                          and mfg_year is not null and condition in ('used','demo') then
                 percentile_cont(0.5) within group (order by price_lakh) filter (where data_consistent)
               else null end as comp_median
        from baseline
        group by brand,model,variant,mfg_year,condition,price_basis
      )
    """
    selected = ""
    if _vehicle_ids is not None:
        selected = " where g.vehicle_id = any(%s::uuid[])"
        params.append(list(_vehicle_ids))
    gap="case when c.comp_median > 0 and c.comparable_count >= 3 then (c.comp_median-g.price_lakh)/c.comp_median*100 else null end"
    rank=f"4*greatest(-10,least(20,coalesce({gap},0)))+5*least(g.source_count,4)+10*coalesce(g.identity_confidence,0)+case when g.km <= 30000 then 5 else 0 end+case when g.owners=1 then 4 else 0 end"
    primary={'price':'g.price_lakh asc nulls last','km':'g.km asc nulls last',
             'year':'g.mfg_year desc nulls last','gap':f'{gap} desc nulls last',
             'match':f'{rank} desc nulls last'}[sort]
    order=primary+',g.price_lakh nulls last,g.observed_at desc,g.vehicle_id,g.price_basis'
    # Required non-null brand/model keys must remain hashable equality joins.
    # Null-safe equality here compares nearly every pair of cohort rows.
    projection="""select g.*,c.comparable_count,c.comp_median,
          row_number() over (order by """+order+""") as result_order from grouped g join cohorts c
          on g.brand=c.brand and g.model=c.model
          and g.variant is not distinct from c.variant and g.mfg_year is not distinct from c.mfg_year
          and g.condition=c.condition and g.price_basis=c.price_basis""" + selected + """
          order by """+order+" limit %s offset %s"
    # One statement gives count and page the same database snapshot, and avoids
    # repeating the projection and a network round trip. The left join retains
    # the count even when a page is empty (including offsets beyond the end).
    summary_sql=""",jsonb_build_object(
        'result_count',count(*),'city_count',count(distinct location),
        'cities',coalesce(jsonb_agg(distinct location) filter (where location is not null),'[]'::jsonb),
        'sources',coalesce((select jsonb_agg(distinct offer->>'source') from grouped cross join lateral jsonb_array_elements(offers) offer),'[]'::jsonb),
        'scope','entire_filtered_index') as search_summary""" if with_summary else ''
    sql=base+("""select page.*,totals.*
        from (select count(*)::bigint as total_count"""+summary_sql+""" from grouped) totals
        left join lateral ("""+projection+") page on true order by page.result_order" if return_count else projection)
    pool_started = time.perf_counter()
    with (nullcontext(_connection) if _connection is not None else _connect()) as conn,conn.cursor() as cur:
        record_duration('pool_wait', time.perf_counter() - pool_started)
        total=None
        if explain:
            cur.execute('explain (analyze, buffers, format json) ' + sql,
                        list(params)+[safe_limit,safe_offset])
            return cur.fetchone()['QUERY PLAN']
        measure_call('db_query', cur.execute, sql,list(params)+[safe_limit,safe_offset])
        raw=[dict(r) for r in cur.fetchall()]
        summary=raw[0].get('search_summary',{}) if raw and with_summary else {}
        if return_count:
            total=int(raw[0]['total_count']) if raw else 0
            for row in raw:
                row.pop('total_count',None)
                row.pop('search_summary',None)
            raw=[row for row in raw if row.get('vehicle_id') is not None]
        rows=[json_inventory_value(row) for row in raw]

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
        row['source_count']=len({o.get('source') for o in offers if o.get('source')})
        row['offer_count']=len(offers)
        for offer in offers:
            name=offer.get("source")
            if name and name not in seen:
                seen.add(name); sources.append({"name":name,"status":"inventory","mode":"inventory",
                    "listings_found":sum(1 for r in rows if any(o.get('source')==name for o in r.get('offers') or []))})
    return (rows,sources,total,summary) if with_summary else ((rows,sources,total) if return_count else (rows,sources))


def iter_inventory(*, query: str = "", condition: str = "both", page_size: int = 500):
    """Background reads require Postgres regardless of web feature flags.

    Each page obeys the same latest-observation and expiry policy as search.
    Database errors propagate; callers must never substitute a JSON snapshot.
    """
    require_database()
    page_size = max(1, min(int(page_size), 2000))
    offset = 0
    while True:
        rows, _ = search_inventory(query=query, condition=condition,
                                  limit=page_size, offset=offset, require_persistence=True)
        if not rows:
            return
        yield rows
        if len(rows) < page_size:
            return
        offset += len(rows)
        if offset > 1_000_000:
            raise RuntimeError("Inventory pagination exceeded supported offset; use an indexed cursor")
