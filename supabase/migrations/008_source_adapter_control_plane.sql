-- Source adapter control plane.
-- A validated website is not automatically a customer-searchable adapter.
create table if not exists public.source_adapters (
  adapter_id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.sources(source_id) on delete cascade,
  adapter_key text not null unique,
  adapter_type text not null default 'catalogue',
  status text not null default 'draft'
    check (status in ('draft','verified','degraded','disabled')),
  version integer not null default 1,
  query_strategy text not null default 'brand_model',
  parser_version text,
  pagination_strategy text,
  supports_brand boolean not null default false,
  supports_model boolean not null default false,
  supports_condition boolean not null default false,
  supports_location boolean not null default false,
  last_verified_at timestamptz,
  last_success_at timestamptz,
  failure_count integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(source_id, adapter_key)
);

create index if not exists idx_source_adapters_status
  on public.source_adapters(status, source_id);

alter table public.source_adapters enable row level security;

-- Existing live sources already have verified production adapters in code.
insert into public.source_adapters (
  source_id, adapter_key, adapter_type, status, query_strategy,
  supports_brand, supports_model, supports_condition, supports_location,
  last_verified_at, metadata
)
select
  source_id,
  source_key || '_builtin',
  'builtin',
  'verified',
  query_strategy,
  true, true, true, true,
  now(),
  jsonb_build_object('bootstrap','existing_live_source')
from public.sources
where enabled=true and adapter_status='live'
on conflict (adapter_key) do nothing;

comment on table public.source_adapters is 'Executable source adapters and their verification state. A discovered source is not customer-searchable until its adapter is verified.';
