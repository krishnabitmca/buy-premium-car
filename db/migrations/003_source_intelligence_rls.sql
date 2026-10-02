-- Lock down source intelligence tables. Backend PostgreSQL/service-role access remains available;
-- customer-facing Supabase API roles receive no direct access by default.
alter table if exists public.sources enable row level security;
alter table if exists public.source_capabilities enable row level security;
alter table if exists public.source_endpoints enable row level security;
alter table if exists public.source_health enable row level security;
alter table if exists public.source_discoveries enable row level security;
