-- Metasearch vehicle identity and provider-offer support.
-- Candidate identities are source-agnostic but only created from sufficiently
-- discriminating evidence. They can later be promoted to confirmed with VIN.

alter table public.vehicles drop constraint if exists vehicles_identity_state_check;
alter table public.vehicles add constraint vehicles_identity_state_check
  check (identity_state in ('provisional','candidate','confirmed','ambiguous'));

drop index if exists public.uq_vehicles_confirmed_identity_key;
create unique index if not exists uq_vehicles_resolved_identity_key
  on public.vehicles(identity_key)
  where identity_key is not null and identity_state in ('candidate','confirmed');

create index if not exists idx_listings_active_verified
  on public.listings(vehicle_id,last_verified_at desc)
  where status='active';

comment on column public.vehicles.identity_state is
  'provisional=source-specific; candidate=multi-signal source-agnostic match; confirmed=VIN/chassis; ambiguous=requires separation/review.';
