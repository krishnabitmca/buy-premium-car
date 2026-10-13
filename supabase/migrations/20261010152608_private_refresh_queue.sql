-- Background work belongs to the server; browser roles cannot access the queue.
alter table public.inventory_refresh_queue enable row level security;
revoke all on table public.inventory_refresh_queue from anon, authenticated;
grant select, insert, update, delete on table public.inventory_refresh_queue to service_role;
