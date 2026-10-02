-- Conservative canonical identity rules.
alter table public.vehicles alter column identity_key drop not null;
alter table public.vehicles drop constraint if exists vehicles_identity_key_key;
alter table public.vehicles
  add column if not exists identity_state text not null default 'provisional'
    check (identity_state in ('provisional','confirmed','ambiguous')),
  add column if not exists identity_evidence jsonb not null default '{}'::jsonb;
create unique index if not exists uq_vehicles_confirmed_identity_key
  on public.vehicles(identity_key)
  where identity_key is not null and identity_state = 'confirmed';
