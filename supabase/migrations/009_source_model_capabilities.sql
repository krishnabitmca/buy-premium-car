-- Source x brand x model capability matrix.
-- A source may support a brand without supporting every model.
create table if not exists public.source_model_capabilities (
  capability_id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.sources(source_id) on delete cascade,
  adapter_id uuid references public.source_adapters(adapter_id) on delete set null,
  brand text not null,
  model text not null,
  condition text not null check (condition in ('used','demo','both')),
  supported boolean not null default true,
  query_template text,
  listing_count integer not null default 0,
  freshness_minutes integer,
  last_verified_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(source_id, brand, model, condition)
);

create index if not exists idx_source_model_cap_lookup
  on public.source_model_capabilities(brand, model, condition, supported);

create index if not exists idx_source_model_cap_source
  on public.source_model_capabilities(source_id, supported);

alter table public.source_model_capabilities enable row level security;

-- Bootstrap existing verified live adapters with an explicit wildcard capability.
-- This is intentionally marked as bootstrap evidence; model-specific verification
-- can replace it later without changing the source lifecycle.
insert into public.source_model_capabilities
  (source_id, adapter_id, brand, model, condition, supported, metadata)
select
  sa.source_id,
  sa.adapter_id,
  '*',
  '*',
  'both',
  true,
  jsonb_build_object('bootstrap','existing_verified_adapter',
                     'requires_model_verification',true)
from public.source_adapters sa
join public.sources s on s.source_id=sa.source_id
where sa.status='verified' and s.enabled=true and s.adapter_status='live'
on conflict (source_id, brand, model, condition) do nothing;

comment on table public.source_model_capabilities is
  'Verified source/brand/model/condition capability matrix. Wildcards are bootstrap capability and should be replaced by observed model-specific evidence.';
