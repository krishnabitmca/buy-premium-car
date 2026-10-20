-- Bounded oldest-first retention candidate traversal; no data deletion.
set local lock_timeout='5s';
set local statement_timeout='30s';
create index idx_scan_generation_retention on public.inventory_scan_generations(captured_at,generation_id);
