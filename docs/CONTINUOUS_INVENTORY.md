# Continuous inventory operations

The production target is a PostgreSQL-backed acquisition pipeline shared by web
and mobile clients. Repository JSON and SQLite outputs are reporting/legacy
artifacts, not a scalable customer inventory database. The legacy daily crawler
and alert processor still need migration; this increment does not remove them.

## Run the database refresh service

Apply the repository migrations and seed the source registry using the existing
bootstrap command before starting workers. Set `SOURCE_INTELLIGENCE_DATABASE_URL`
only on the backend. Never expose the database URL in the browser/mobile bundle.

```sh
python -m src.inventory_service --limit 10 --interval-seconds 60
```

For a finite smoke check:

```sh
python -m src.inventory_service --limit 10 --once
```

This service schedules India-wide work even without customer traffic, then
consumes queued source/intent jobs. Multiple processes can use PostgreSQL
`FOR UPDATE SKIP LOCKED`; each process fetches one source at a time. The existing
15-minute workflow remains a finite execution alternative. Do not enable both
at scale until per-domain concurrency and rate limits have been measured.

Full registry configuration reaches each adapter, including parser strategy,
active endpoints and query templates. Only enabled, live sources with a verified
adapter can be claimed. Discovery candidates do not automatically become trusted
inventory. The existing source-discovery workflow remains responsible for finding
and staging new sources.

## Refresh and failure behavior

- Freshness is tracked per source/brand/model/condition/destination job, using
  `metadata.last_success_at`. A successful empty scan is a successful scan;
  a fresh listing in another search segment does not suppress this refresh.
- Jobs are claimed immediately before execution. One source failure is recorded
  and does not abort the remaining batch.
- Failures retry after 10 and 20 minutes, up to three total attempts. A running
  claim older than 30 minutes is recovered when a worker starts a batch.
- Exhausted jobs remain failed for operator inspection. After fixing the cause,
  an operator may explicitly reset the specific job to queued with attempt count
  zero. The scheduler never silently resets exhausted failures.
- Completion checks the attempt number, preventing an expired worker from
  completing another worker's claim. Fetch/ingestion is at least once, so a crash
  between ingestion and completion can leave duplicate historical observations.

The 30-minute claim is a recovery timeout, not a heartbeat lease. Long-running
fetches can outlive it. Before expanding worker concurrency, add heartbeat leases,
fenced ingestion and source/domain rate limiting. Recovery and retry data is kept
in Postgres; no flat-file queue is used.

## PAN-India launch gates

This service is an implementation step, not proof of national coverage or a
production deployment. Remaining work includes:

1. Consolidate daily acquisition and alert reads onto canonical Postgres inventory.
2. Replace request-time fallback with an explicitly documented freshness policy,
   coverage manifests, asynchronous demand refresh and customer-visible status.
3. Preserve marketplace listing IDs and price basis; validate canonical identity
   against real cross-marketplace examples and retain ambiguous matches separately.
4. Fix watch matching units/constraints and verify ownership, consent and delivery.
5. Protect the existing refresh queue with RLS/grants in a forward migration;
   use a restricted backend database role. Do not expose queue access to clients.
6. Add per-domain budgets, heartbeat leases, monitoring, backup/restore checks and
   representative load tests. Measure successful crawls, freshness and region/model
   coverage rather than claiming that all Indian inventory is indexed.
7. Complete responsive design states and mobile API verification. Distinguish
   lowest observed asking price from the strongest evidence-backed deal signal.
8. Verify a preview and production deployment. The existing Vercel endpoint's
   HTTP 402 response remains a separate launch blocker.
