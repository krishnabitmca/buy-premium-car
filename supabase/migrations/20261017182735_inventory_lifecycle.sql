-- Private, durable listing revalidation and shared background crawl pacing.
create table public.inventory_listing_refresh (
  listing_id uuid primary key references public.listings(listing_id) on delete cascade,
  status text not null default 'queued' check(status in ('queued','running','completed','failed')),
  due_at timestamptz not null default now(),
  lease_token uuid,
  lease_expires_at timestamptz,
  attempt_count integer not null default 0,
  failure_count integer not null default 0,
  missing_count integer not null default 0,
  last_checked_at timestamptz,
  last_outcome text,
  last_error text
);
create index inventory_listing_refresh_due on public.inventory_listing_refresh(due_at,listing_id)
  where status in ('queued','failed','completed');
create index inventory_listing_refresh_leases on public.inventory_listing_refresh(lease_expires_at)
  where status='running';
create table public.inventory_crawl_leases (
  domain text primary key,
  lease_token uuid not null,
  lease_expires_at timestamptz not null,
  next_allowed_at timestamptz not null default now()
);
create table public.inventory_pipeline_runs (
  run_id uuid primary key default gen_random_uuid(),
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null default 'running' check(status in ('running','ok','degraded','failed')),
  summary jsonb not null default '{}'::jsonb
);
create index inventory_pipeline_runs_recent on public.inventory_pipeline_runs(started_at desc);
create index listings_source_url_lookup on public.listings(source_id,url);
do $$ declare t text; begin
  foreach t in array array['inventory_listing_refresh','inventory_crawl_leases','inventory_pipeline_runs'] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('revoke all on public.%I from public,anon,authenticated',t);
    execute format('grant select,insert,update,delete on public.%I to service_role',t);
    if exists(select 1 from pg_roles where rolname='carscanner_free_test_runtime') then
      execute format('grant select,insert,update,delete on public.%I to carscanner_free_test_runtime',t);
      execute format('create policy server_inventory_lifecycle on public.%I to carscanner_free_test_runtime using(true) with check(true)',t);
    end if;
  end loop;
end $$;
