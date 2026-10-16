-- Durable, global daily pilot quota; no prompts, identities or API keys stored.
create table public.buyer_ai_daily_usage (
  usage_day date primary key,
  calls integer not null check (calls between 1 and 30)
);
alter table public.buyer_ai_daily_usage enable row level security;
revoke all on public.buyer_ai_daily_usage from public, anon, authenticated;
grant select, insert, update on public.buyer_ai_daily_usage to service_role;
do $$ begin
  if exists(select 1 from pg_roles where rolname='carscanner_free_test_runtime') then
    grant select, insert, update on public.buyer_ai_daily_usage to carscanner_free_test_runtime;
    create policy server_ai_usage on public.buyer_ai_daily_usage
      to carscanner_free_test_runtime using (true) with check (true);
  end if;
end $$;
