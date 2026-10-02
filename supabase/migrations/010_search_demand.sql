-- Aggregated customer demand signals for source-discovery prioritization.
-- No user identifiers are stored. Demand is bucketed by intent dimensions.
create table if not exists public.search_demand (
  demand_id bigserial primary key,
  hour_bucket timestamptz not null,
  brand text not null default '',
  model text not null default '',
  condition text not null default 'both'
    check (condition in ('used','demo','both')),
  budget_band text not null default 'unspecified',
  destination_state text not null default '',
  search_count bigint not null default 0,
  inventory_hit_count bigint not null default 0,
  source_count_sum bigint not null default 0,
  last_searched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique(hour_bucket, brand, model, condition, budget_band, destination_state)
);

create index if not exists idx_search_demand_priority
  on public.search_demand(last_searched_at desc, search_count desc);

create index if not exists idx_search_demand_intent
  on public.search_demand(brand, model, condition, last_searched_at desc);

alter table public.search_demand enable row level security;

create or replace function public.record_search_demand(
  p_hour_bucket timestamptz,
  p_brand text,
  p_model text,
  p_condition text,
  p_budget_band text,
  p_destination_state text,
  p_inventory_hit_count integer,
  p_source_count integer
) returns void
language sql
security definer
set search_path = public
as $$
  insert into public.search_demand(
    hour_bucket, brand, model, condition, budget_band, destination_state,
    search_count, inventory_hit_count, source_count_sum, last_searched_at
  )
  values(
    p_hour_bucket,
    coalesce(lower(trim(p_brand)), ''),
    coalesce(lower(trim(p_model)), ''),
    coalesce(lower(trim(p_condition)), 'both'),
    coalesce(lower(trim(p_budget_band)), 'unspecified'),
    coalesce(lower(trim(p_destination_state)), ''),
    1,
    greatest(coalesce(p_inventory_hit_count, 0), 0),
    greatest(coalesce(p_source_count, 0), 0),
    now()
  )
  on conflict(hour_bucket, brand, model, condition, budget_band, destination_state)
  do update set
    search_count = public.search_demand.search_count + 1,
    inventory_hit_count = public.search_demand.inventory_hit_count + excluded.inventory_hit_count,
    source_count_sum = public.search_demand.source_count_sum + excluded.source_count_sum,
    last_searched_at = now();
$$;

comment on table public.search_demand is
  'Privacy-preserving aggregate search demand used to prioritize source discovery. No user IDs are stored.';

-- Demand writes are backend-only; prevent public/anonymous clients from
-- forging discovery-priority signals.
revoke all on function public.record_search_demand(
  timestamptz, text, text, text, text, text, integer, integer
) from public, anon, authenticated;
grant execute on function public.record_search_demand(
  timestamptz, text, text, text, text, text, integer, integer
) to service_role;
