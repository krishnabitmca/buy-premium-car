-- Server-only operational scheduling evidence on the existing RLS-protected
-- discovery table. Existing grants/policies are unchanged.
alter table public.source_discoveries
  add column last_probe_at timestamptz,
  add column probe_token uuid,
  add column probe_result jsonb not null default '{}'::jsonb;

comment on column public.source_discoveries.last_probe_at is
  'Actual source validation attempt start; discovered_at remains discovery history.';
comment on column public.source_discoveries.probe_token is
  'Fences completion after a 30-minute interrupted-probe lease is recovered.';
