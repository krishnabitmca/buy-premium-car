-- Private audit of accepted scan writes. This never grants completeness or
-- absence-retirement authority. No search-projection revision triggers here.
set local lock_timeout = '5s';
set local statement_timeout = '30s';
create unique index if not exists idx_refresh_source_identity
  on public.inventory_refresh_queue(refresh_id,source_id);
create unique index if not exists idx_listing_source_identity
  on public.listings(listing_id,source_id);
create unique index if not exists idx_observation_listing_source_identity
  on public.vehicle_observations(observation_id,listing_id,source_id);

create table public.inventory_scan_generations (
  generation_id uuid primary key,
  source_id uuid not null,
  refresh_id bigint not null,
  scope_fingerprint text not null check (scope_fingerprint ~ '^[0-9a-f]{64}$'),
  started_at timestamptz not null,
  captured_at timestamptz not null default now(),
  contract_version integer not null check (contract_version=1),
  state text not null default 'partial' check (state in ('partial','exhausted_unverified')),
  legacy_partial_history boolean not null,
  completeness_verified boolean not null default false check (not completeness_verified),
  absence_reconciliation_permitted boolean not null default false check (not absence_reconciliation_permitted),
  last_batch_at timestamptz,
  unique(generation_id,source_id,refresh_id),
  foreign key(refresh_id,source_id)
    references public.inventory_refresh_queue(refresh_id,source_id) on delete restrict
);
create index idx_scan_generation_scope
  on public.inventory_scan_generations(source_id,scope_fingerprint,started_at desc);
create index idx_scan_generation_refresh
  on public.inventory_scan_generations(refresh_id,source_id);

create table public.inventory_scan_batches (
  batch_id uuid primary key,
  generation_id uuid not null,
  source_id uuid not null,
  refresh_id bigint not null,
  attempt_count integer not null check(attempt_count>0),
  claim_started_at timestamptz not null,
  pages_fetched integer not null default 0 check(pages_fetched>=0),
  accepted_count integer not null default 0 check(accepted_count>=0),
  terminal_reason text check(terminal_reason in ('pending_pages','frontier_exhausted')),
  completed_at timestamptz,
  unique(refresh_id,attempt_count,claim_started_at),
  unique(batch_id,source_id),
  foreign key(generation_id,source_id,refresh_id)
    references public.inventory_scan_generations(generation_id,source_id,refresh_id) on delete cascade
);
create index idx_scan_batch_generation
  on public.inventory_scan_batches(generation_id,completed_at);

create table public.inventory_scan_memberships (
  batch_id uuid not null,
  source_id uuid not null,
  listing_id uuid not null,
  observation_id bigint not null,
  evidence_kind text not null check(evidence_kind in ('positive','explicit_negative')),
  primary key(batch_id,observation_id),
  foreign key(batch_id,source_id)
    references public.inventory_scan_batches(batch_id,source_id) on delete cascade,
  foreign key(observation_id,listing_id,source_id)
    references public.vehicle_observations(observation_id,listing_id,source_id) on delete restrict,
  foreign key(listing_id,source_id)
    references public.listings(listing_id,source_id) on delete restrict
);
create index idx_scan_membership_listing
  on public.inventory_scan_memberships(listing_id,batch_id);
create index idx_scan_membership_observation
  on public.inventory_scan_memberships(observation_id);

alter table public.inventory_scan_generations enable row level security;
alter table public.inventory_scan_batches enable row level security;
alter table public.inventory_scan_memberships enable row level security;
revoke all on public.inventory_scan_generations,public.inventory_scan_batches,
  public.inventory_scan_memberships from public;
do $$
declare role_name text;
begin
  foreach role_name in array array['anon','authenticated'] loop
    if exists(select 1 from pg_roles where rolname=role_name) then
      execute format('revoke all on public.inventory_scan_generations, public.inventory_scan_batches, public.inventory_scan_memberships from %I',role_name);
    end if;
  end loop;
end $$;
