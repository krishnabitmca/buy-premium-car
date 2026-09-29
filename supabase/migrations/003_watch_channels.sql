-- Tie notification preferences to the individual Car Watch.
-- Keep the older user-level table for backward compatibility, but new delivery
-- decisions should use this watch-scoped table.
create table if not exists public.watch_channel_preferences (
  preference_id uuid primary key default gen_random_uuid(),
  watch_id uuid not null references public.deal_watches(watch_id) on delete cascade,
  channel text not null check (channel in ('email','whatsapp')),
  enabled boolean not null default false,
  frequency text not null default 'instant' check (frequency in ('instant','daily','both')),
  consent_at timestamptz,
  consent_source text,
  updated_at timestamptz not null default now(),
  unique(watch_id, channel)
);

create index if not exists idx_watch_channel_preferences_watch
  on public.watch_channel_preferences(watch_id, enabled);

alter table public.watch_channel_preferences enable row level security;

comment on table public.watch_channel_preferences is
  'Per-watch notification channel preferences and consent.';
