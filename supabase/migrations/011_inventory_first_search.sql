-- Inventory-first search indexes.
-- Keeps customer reads bounded as inventory grows to millions of listings.

create index if not exists idx_vehicles_active_search
  on public.vehicles (brand, model, condition, status, last_seen_at desc);

create index if not exists idx_observations_fresh_verified
  on public.vehicle_observations (vehicle_id, observed_at desc)
  where live_verified=true and sold_signal=false;

create index if not exists idx_listings_active_vehicle
  on public.listings (vehicle_id, status, last_seen_at desc)
  where status='active';

comment on index public.idx_observations_fresh_verified is
  'Supports freshest verified observation lookup for inventory-first customer search.';
