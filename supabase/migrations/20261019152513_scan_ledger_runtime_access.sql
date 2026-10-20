-- Existing private worker role only. Apply remotely only after owner approval.
set local lock_timeout='5s';
set local statement_timeout='30s';
do $$
declare t text;
begin
  if exists(select 1 from pg_roles where rolname='carscanner_free_test_runtime') then
    foreach t in array array['inventory_scan_generations','inventory_scan_batches','inventory_scan_memberships'] loop
      execute format('grant select,insert,update on public.%I to carscanner_free_test_runtime',t);
      execute format('create policy scan_ledger_runtime_select on public.%I for select to carscanner_free_test_runtime using(true)',t);
      execute format('create policy scan_ledger_runtime_insert on public.%I for insert to carscanner_free_test_runtime with check(true)',t);
      execute format('create policy scan_ledger_runtime_update on public.%I for update to carscanner_free_test_runtime using(true) with check(true)',t);
    end loop;
  end if;
end $$;
-- No browser grant, DELETE/TRUNCATE, role membership, credential or RLS bypass.
