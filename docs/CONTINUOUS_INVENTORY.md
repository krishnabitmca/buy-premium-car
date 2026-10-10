# Continuous inventory operations

The production target is a PostgreSQL-backed acquisition pipeline shared by web
and mobile clients. Repository JSON and SQLite outputs are reporting/legacy
artifacts, not a scalable customer inventory database. Production daily acquisition
and watch matching now use canonical Postgres inventory. The broad browser crawler
is retained only as the explicit `src.legacy_reports` diagnostic command.

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

1. Replace request-time fallback with an explicitly documented freshness policy,
   coverage manifests, asynchronous demand refresh and customer-visible status.
2. Validate canonical identity
   against real cross-marketplace examples and retain ambiguous matches separately.
3. Verify watch ownership, consent and provider delivery end to end. Watch criteria
   now enforce units, mileage, owner limits and explicit condition, but radius
   constraints require measured distance and currently fail closed when unavailable.
4. Protect the existing refresh queue with RLS/grants in a forward migration;
   use a restricted backend database role. Do not expose queue access to clients.
5. Add per-domain budgets, heartbeat leases, monitoring, backup/restore checks and
   representative load tests. Measure successful crawls, freshness and region/model
   coverage rather than claiming that all Indian inventory is indexed.
6. Complete responsive design states and mobile API verification. Distinguish
   lowest observed asking price from the strongest evidence-backed deal signal.
7. Verify a preview and production deployment. The existing Vercel endpoint's
   HTTP 402 response remains a separate launch blocker.

## Daily acquisition and watch migration

```sh
python -m src.main --limit 100
python -m src.main --limit 100 --export-json work/inventory-export.json
python -m scripts.process_alerts --mode instant --dry-run
python -m scripts.process_alerts --mode daily --dry-run
```

Watch evaluation requires the inventory database URL even if the web inventory
feature flag is disabled. Watch/user/channel preferences are read from Supabase's
Postgres-backed REST API using the existing server-only credentials. Configure
`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for the same database project as
`SOURCE_INTELLIGENCE_DATABASE_URL`; this pairing must be verified in staging.
Dry runs read watches/inventory and evaluate matches without writing events or
calling providers. Database errors propagate; a stale JSON export is never used.

The daily workflow runs canonical acquisition and daily/both watches. The
15-minute refresh workflow runs instant/both watches after refresh. These are
polling intervals, not a promise of immediate provider delivery. JSON exports are
short-lived diagnostic workflow artifacts; no inventory files are pushed to main.
Source discovery remains in the independent source-expansion workflow. Initial
registry bootstrap is an explicit administrative step, not a daily overwrite of
operator-maintained source settings.

Marketplace stock IDs and price basis now survive adapter ingestion. A stable ID
can adopt an older URL-keyed listing when canonical identity matches, preserving
its history instead of exposing both old and new prices. Ambiguous identity
transitions still require operator review. Comparison medians require at least
three current canonical vehicles with the same brand/model/variant/year/condition
and price basis, and are calculated before watch budget filtering and pagination.
These are observed cohort medians, not appraised values or transaction prices;
trim/mileage/identity accuracy remains a launch validation requirement.

Watch/event deduplication uses canonical vehicle identity plus price/condition/
price-basis version, so repeated scans at one price do not resend, while a newly
qualifying price can alert again. Existing legacy `deal_match` events do not have
this version key; rollout can produce one new alert for an already alerted car.
Unsubscribed users, disabled channels and channels without recorded consent are
skipped. “Any” means an eligible criteria match; it does not imply a bargain.

The existing alert outbox still needs atomic worker claims and recovery of pending
deliveries. Provider acceptance remains stored as `sent`, not proof of delivery;
webhook receipts and WhatsApp retry/idempotency need verification. Do not run
multiple delivery processes for the same watches before those launch gates pass.
Offset pagination observes a changing inventory; large-scale workers should move
to indexed cursors or a consistent database snapshot to avoid skipped/duplicate
rows during simultaneous price updates. Per-event uniqueness suppresses duplicate
notification creation, but does not provide a snapshot of all national inventory.
