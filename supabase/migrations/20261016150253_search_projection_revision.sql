-- A transactional fence for derived search projections. Never exposed to browsers.
create table public.search_projection_revision (
  singleton boolean primary key default true check (singleton),
  revision bigint not null default 1
);
insert into public.search_projection_revision(singleton) values(true);
alter table public.search_projection_revision enable row level security;
revoke all on public.search_projection_revision from public, anon, authenticated;
grant select, update on public.search_projection_revision to service_role;
create function public.advance_search_projection_revision() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
  update public.search_projection_revision set revision = revision + 1 where singleton;
  return null;
end;
$$;
revoke all on function public.advance_search_projection_revision() from public, anon, authenticated;
-- Statement triggers avoid updating the fence once for every imported row.
create trigger search_revision_vehicles after insert or update or delete or truncate on public.vehicles
for each statement execute function public.advance_search_projection_revision();
create trigger search_revision_listings after insert or update or delete or truncate on public.listings
for each statement execute function public.advance_search_projection_revision();
create trigger search_revision_observations after insert or update or delete or truncate on public.vehicle_observations
for each statement execute function public.advance_search_projection_revision();
create trigger search_revision_sources after insert or update or delete or truncate on public.sources
for each statement execute function public.advance_search_projection_revision();
do $$ begin
  if exists(select 1 from pg_roles where rolname='carscanner_free_test_runtime') then
    grant select, update on public.search_projection_revision to carscanner_free_test_runtime;
    grant execute on function public.advance_search_projection_revision() to carscanner_free_test_runtime;
    create policy server_revision on public.search_projection_revision
      to carscanner_free_test_runtime using (true) with check (true);
  end if;
end $$;
