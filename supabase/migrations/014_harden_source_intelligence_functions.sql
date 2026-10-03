-- Harden source-intelligence freshness function search_path.
create or replace function public.inventory_freshness_state(
  p_last_verified_at timestamptz,
  p_source_id uuid
) returns text
language sql
stable
set search_path = public
as $$
  select case
    when p_last_verified_at is null then 'expired'
    when extract(epoch from (now() - p_last_verified_at))/60
         <= coalesce(s.freshness_target_minutes,360) then 'fresh'
    when extract(epoch from (now() - p_last_verified_at))/60
         <= coalesce(s.stale_after_minutes,1440) then 'aging'
    when extract(epoch from (now() - p_last_verified_at))/60
         <= coalesce(s.expire_after_minutes,10080) then 'stale'
    else 'expired'
  end
  from public.sources s
  where s.source_id=p_source_id;
$$;
