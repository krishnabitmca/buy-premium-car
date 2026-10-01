-- PostgreSQL source intelligence registry.
-- Supabase/PostgreSQL compatible.
create extension if not exists pgcrypto;

create table if not exists public.sources (
  source_id uuid primary key default gen_random_uuid(),
  source_key text not null unique,
  name text not null,
  url text not null,
  tier smallint not null default 2,
  source_type text not null,
  adapter_status text not null default 'candidate'
    check (adapter_status in ('live','candidate','discovery_only','disabled')),
  geography text not null default 'india',
  query_strategy text not null default 'brand_model',
  vehicle_link_pattern text,
  priority integer not null default 50,
  enabled boolean not null default true,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  last_validated_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.source_capabilities (
  source_id uuid not null references public.sources(source_id) on delete cascade,
  capability_type text not null check (capability_type in ('condition','segment','brand')),
  capability_value text not null,
  primary key (source_id, capability_type, capability_value)
);

create table if not exists public.source_endpoints (
  endpoint_id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.sources(source_id) on delete cascade,
  url text not null,
  endpoint_type text not null default 'catalogue',
  is_active boolean not null default true,
  query_template text,
  last_checked_at timestamptz,
  last_http_status integer,
  metadata jsonb not null default '{}'::jsonb,
  unique(source_id, url)
);

create table if not exists public.source_health (
  health_id bigserial primary key,
  source_id uuid not null references public.sources(source_id) on delete cascade,
  checked_at timestamptz not null default now(),
  status text not null check (status in ('healthy','degraded','unhealthy','blocked','unknown')),
  http_status integer,
  latency_ms integer,
  listings_found integer not null default 0,
  parser_ok boolean,
  inventory_verified boolean,
  error_message text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.source_discoveries (
  discovery_id uuid primary key default gen_random_uuid(),
  source_id uuid references public.sources(source_id) on delete set null,
  domain text not null,
  url text not null,
  title text,
  snippet text,
  query text,
  source_type text,
  condition text,
  segment text,
  brand_hint text,
  candidate_confidence numeric(5,4),
  discovered_at timestamptz not null default now(),
  status text not null default 'discovered'
    check (status in ('discovered','classified','validated','rejected','promoted')),
  unique(domain, url)
);

create index if not exists idx_sources_status_priority on public.sources(enabled, adapter_status, priority desc);
create index if not exists idx_source_capabilities_lookup on public.source_capabilities(capability_type, capability_value);
create index if not exists idx_source_health_latest on public.source_health(source_id, checked_at desc);
create index if not exists idx_source_discoveries_status on public.source_discoveries(status, candidate_confidence desc);

create or replace view public.source_health_latest as
select distinct on (source_id)
  source_id, checked_at, status, http_status, latency_ms,
  listings_found, parser_ok, inventory_verified, error_message, metadata
from public.source_health
order by source_id, checked_at desc;

comment on table public.sources is 'System of record for CarScanner source intelligence.';
comment on table public.source_discoveries is 'Deep-discovery candidates before adapter validation/promotion.';
