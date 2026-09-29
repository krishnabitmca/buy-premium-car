-- Private bearer access for "My Car Watches".
-- Raw tokens are never stored; only a SHA-256 digest is persisted.
alter table public.deal_watch_users
  add column if not exists access_token_hash text;

create unique index if not exists idx_deal_watch_users_access_token_hash
  on public.deal_watch_users(access_token_hash)
  where access_token_hash is not null;

comment on column public.deal_watch_users.access_token_hash
  is 'SHA-256 hash of the private bearer token used to manage a user''s watches.';
