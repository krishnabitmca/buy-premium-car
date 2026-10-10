-- Dedicated backend login; password is provisioned separately and never committed.
do $$ begin
  if not exists (select 1 from pg_roles where rolname='carscanner_free_test_runtime') then
    create role carscanner_free_test_runtime nologin nosuperuser nocreatedb nocreaterole noinherit;
  end if;
end $$;
grant usage on schema public to carscanner_free_test_runtime;
do $$
declare table_name text;
begin
  foreach table_name in array array['sources','source_capabilities','source_endpoints','source_health','source_discoveries','vehicles','listings','vehicle_observations','source_adapters','source_model_capabilities','search_demand','inventory_refresh_queue','deal_watch_users','deal_watches','channel_preferences','watch_channel_preferences','alert_events']
  loop
    execute format('grant select, insert, update, delete on table public.%I to carscanner_free_test_runtime', table_name);
    if not exists (select 1 from pg_policies where schemaname='public' and tablename=table_name and policyname='carscanner_private_runtime') then
      execute format('create policy carscanner_private_runtime on public.%I for all to carscanner_free_test_runtime using (true) with check (true)', table_name);
    end if;
  end loop;
end $$;
grant execute on all functions in schema public to carscanner_free_test_runtime;
