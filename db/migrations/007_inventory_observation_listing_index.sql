create index if not exists idx_observations_listing_time
  on public.vehicle_observations(listing_id, observed_at desc)
  where listing_id is not null;
