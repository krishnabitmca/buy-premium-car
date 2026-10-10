-- Server APIs need explicit privileges independently of RLS.
grant select, insert, update, delete on public.deal_watch_users, public.deal_watches, public.channel_preferences, public.watch_channel_preferences, public.alert_events to service_role;
