-- Adapter health and circuit-breaker state.
alter table public.source_adapters
  add column if not exists consecutive_failures integer not null default 0,
  add column if not exists total_successes bigint not null default 0,
  add column if not exists total_failures bigint not null default 0,
  add column if not exists last_failure_at timestamptz,
  add column if not exists last_error text,
  add column if not exists last_latency_ms integer,
  add column if not exists circuit_state text not null default 'closed'
    check (circuit_state in ('closed','open','half_open')),
  add column if not exists circuit_opened_at timestamptz,
  add column if not exists next_retry_at timestamptz;

create index if not exists idx_source_adapters_execution_health
  on public.source_adapters(status, circuit_state, next_retry_at);

comment on column public.source_adapters.circuit_state is
  'closed=normal execution, open=temporarily blocked after repeated failures, half_open=single probe allowed';

comment on column public.source_adapters.consecutive_failures is
  'Failures since the most recent successful adapter execution.';
