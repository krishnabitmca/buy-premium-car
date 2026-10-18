# Production HTTP runtime

Docker starts:

```sh
gunicorn --config gunicorn.conf.py wsgi:application
```

It binds `HOST` (default `0.0.0.0`) and `PORT` (default `10000`). One process/four
gthread request threads is the initial configuration. `CARSCANNER_WEB_WORKERS`
allows 1–4 processes and `CARSCANNER_WEB_THREADS` 1–16 threads. These bounds prevent
accidental unlimited configuration; they are not a recommendation to use the
maximum on a small instance. Each worker can have its own eight-connection database
pool and background executors; include the crawler and other deployments in the
total connection/memory budget. No application preload is used.

The existing APIs and static allowlist are shared through a WSGI adapter. Large
request bodies are rejected before buffering; API-specific validation still runs.
Responses contain `X-CarScanner-Runtime: wsgi`. Access logs omit URLs, query strings
and headers. Existing handler-level privacy and authentication gates still apply.

The server bounds threads, active clients and socket backlog; this does not provide
distributed per-user rate limits or a universal request deadline. Gunicorn's
45-second timeout detects a silent worker, rather than cancelling every slow
gthread request. Existing database/provider timeouts remain important. Graceful
restart allows 25 seconds for in-flight work, then the process server can kill a
worker. A process restart cannot undo already committed external side effects.

## Liveness and readiness

API admission is limited to three active handlers per WSGI worker (ADR 021).
Additional requests receive a no-store 503 with `Retry-After: 1` before their body
is read. Preflight, `/api/version` and non-API routes are exempt. The default four
threads leave dispatch headroom, but socket queuing and dependency latency can
still delay health requests. This worker-local cap is not a distributed rate
limit; fewer request threads remove the intended headroom.

The browser retries read-only catalogue/search overload responses up to five
times within existing overall deadlines, honoring a short Retry-After with jitter.
Watch and AI mutations are never replayed by this helper.

- `/health`: process liveness, independent of database availability.
- `/ready`: database accessibility and canonical table presence. Returns 200/503
  and small generic JSON. It performs no marketplace requests or inventory writes.
- `/api/version`: deployed commit, unchanged contract.

Readiness uses a short pool checkout and statement timeout. It does not validate
every migration/column, freshness, source coverage, index lag or actual search
latency. Platform health-check configuration remains unchanged in this increment;
monitor readiness before choosing it as the restart/routing signal. A shared
database outage can affect every replica simultaneously.

## Local and CI verification

On Windows, keep `python render_server.py` for the existing preview. The adapter
is unit-tested there. Gunicorn requires Unix and is verified by Linux CI with the
same configuration as Docker. CI exercises readiness, real PostgreSQL search,
graceful SIGTERM drain and the production-adapter browser journeys.

This release changes runtime code only. The owner selected a $150/month planning
ceiling; paid web/worker/database upgrades still require explicit activation
approval. This commit does not provision an always-on crawler, pay for Elastic,
change model billing or claim national capacity.
