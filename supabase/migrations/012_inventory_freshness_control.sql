-- Freshness-aware inventory control plane.
-- Customer reads remain inventory-first; background crawlers use these fields
-- to decide what needs verification next.

alter table public.sources
  add column if not exists freshness_target_minutes integer not null default 360,
  add column if not exists stale_after_minutes integer not null default 1440,
  add column if not exists expire_after_minutes integer not null default 10080;

alter table public.listings
  add column if not exists freshness_state text not null default 'fresh'
    check (freshness_state in ('fresh','aging','stale','expired')),
  add column if not exists refresh_priority numeric(12,4) not null default 0;

create index if not exists idx_listings_freshness_queue
  on public.listings(freshness_state, refresh_priority desc, last_verified_at asc)
  where status='active';

create index if not exists idx_listings_source_freshness
  on public.listings(source_id, freshness_state, last_verified_at asc)
  where status='active';

-- Refresh requests are deduplicated by source + intent. A single hot model
-- cannot create thousands of concurrent marketplace crawls.
create table if not exists public.inventory_refresh_queue (
  refresh_id bigserial primary key,
  source_id uuid not null references public.sources(source_id) on delete cascade,
  brand text not null default '',
  model text not null default '',
  condition text not null default 'both'
    check (condition in ('used','demo','both')),
  destination_state text not null default '',
  priority numeric(12,4) not null default 0,
  reason text not null default 'stale',
  status text not null default 'queued'
    check (status in ('queued','running','completed','failed','cancelled')),
  requested_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  attempt_count integer not null default 0,
  last_error text,
  metadata jsonb not null default '{}'::jsonb,
  unique(source_id, brand, model, condition, destination_state)
);

create index if not exists idx_refresh_queue_ready
  on public.inventory_refresh_queue(status, priority desc, requested_at asc)
  where status='queued';

create index if not exists idx_refresh_queue_source
  on public.inventory_refresh_queue(source_id, status);

-- Convert elapsed verification age into a customer-safe state.
create or replace function public.inventory_freshness_state(
  p_last_verified_at timestamptz,
  p_source_id uuid
) returns text
language sql
stable
as $$
  select case
    when p_last_verified_at is null then 'expired'
    when extract(epoch from (now() - p_last_verified_at))/60
         <= coalesce(s.freshness_target_minutes,360) then 'fresh'
    when extract(epoch from (now() - p_last_verified_at))/60
         <= coalesce(s.stale_after_minutes,1440) then 'aging'
    when extract(epoch from (now() - p_last_verified_at))/60
         <= coalesce(s.expire_after_minutes,10080) then 'stale'
    else 'expired'
  end
  from public.sources s
  where s.source_id=p_source_id;
$$;

comment on table public.inventory_refresh_queue is
  'Deduplicated background refresh work; customer requests should enqueue, not crawl synchronously.';
