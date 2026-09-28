-- Supabase schema for persistent Used & Demo Car Deal Watches.
-- Keep RLS enabled; the server-side API uses the service role key.
create extension if not exists pgcrypto;

create table if not exists public.deal_watch_users (
  user_id uuid primary key default gen_random_uuid(),
  email text not null unique,
  phone_e164 text,
  status text not null default 'active' check (status in ('active','paused','unsubscribed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.deal_watches (
  watch_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.deal_watch_users(user_id) on delete cascade,
  name text not null,
  category text not null default 'automotive',
  natural_language_request text,
  constraints jsonb not null default '{}'::jsonb,
  target_discount_pct numeric,
  alert_quality text not null default 'exceptional' check (alert_quality in ('any','good','exceptional')),
  frequency text not null default 'instant' check (frequency in ('instant','daily','both')),
  status text not null default 'active' check (status in ('active','paused','archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.channel_preferences (
  preference_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.deal_watch_users(user_id) on delete cascade,
  channel text not null check (channel in ('email','whatsapp')),
  enabled boolean not null default false,
  frequency text not null default 'instant' check (frequency in ('instant','daily','both')),
  consent_at timestamptz,
  consent_source text,
  updated_at timestamptz not null default now(),
  unique(user_id, channel)
);

create table if not exists public.alert_events (
  alert_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.deal_watch_users(user_id) on delete cascade,
  watch_id uuid not null references public.deal_watches(watch_id) on delete cascade,
  listing_id text not null,
  channel text not null check (channel in ('email','whatsapp')),
  event_type text not null default 'deal_match',
  status text not null default 'pending' check (status in ('pending','sent','failed','skipped')),
  payload jsonb not null default '{}'::jsonb,
  provider_message_id text,
  error_message text,
  created_at timestamptz not null default now(),
  sent_at timestamptz,
  unique(watch_id, listing_id, channel, event_type)
);

create index if not exists idx_deal_watches_user_status on public.deal_watches(user_id, status);
create index if not exists idx_channel_preferences_user on public.channel_preferences(user_id, enabled);
create index if not exists idx_alert_events_status on public.alert_events(status, created_at desc);

alter table public.deal_watch_users enable row level security;
alter table public.deal_watches enable row level security;
alter table public.channel_preferences enable row level security;
alter table public.alert_events enable row level security;

comment on table public.deal_watches is 'Persistent customer-specific used/demo car Deal Intents.';
comment on table public.alert_events is 'Alert outbox and delivery audit; unique constraint suppresses duplicate alerts.';
