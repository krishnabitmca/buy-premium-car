# Continuous inventory operations

## Coverage control and capacity evidence

Run `python -m src.inventory_coverage --operations-only --output coverage/operations.json
--markdown coverage/operations.md` for a consistent read-only snapshot of observed
source/location/brand/model/condition cells, declared queue/catalogue scopes,
prioritized repair work and renewal capacity. The regular refresh workflow uploads
both artifacts after every run; the daily national report includes this evidence.
The default full report also retains the make-level customer-search audit.

`--renewal-limit 10 --interval-minutes 15` describes a hypothetical configured
budget, not a measured scheduling SLA. Per-condition demand is the recurring
individual-check scenario, with retry readiness and classification/shared-URL
exceptions reported separately. Bulk catalogue batches can renew many offers at
once; source parser yield and origin pacing determine effective throughput.

The matrix is sparse observed evidence. Missing combinations are unknown. Raw
seller location labels are not normalized cities. Declared advertised scopes
retain original evidence URLs; visiting a landing page does not complete its
catalogue. Market coverage percentages remain null until independent eligible
listing samples establish a valid denominator. Source claims are not added into
one market total. See ADR 016 for definitions and workload reservations.

## Listing renewal and availability lifecycle

Apply `20261017182735_inventory_lifecycle.sql` before deploying this worker.
The server-only tables hold listing renewal jobs, origin crawl leases and run
evidence; they have no anon/authenticated access. Existing canonical history is
preserved. Catalogue ingestion and its cursor commit atomically after claim
ownership is rechecked. Listing renewal uses tokens and checks whether catalogue
ingestion has supplied newer evidence before writing.

Run `python -m src.inventory_lifecycle --limit 10 --report coverage/lifecycle.json`
for expiry maintenance, bounded renewal and an operational report. Targets are
six-hour used and three-hour demo checks (or stricter source targets); hard search
expiry caps default to 48-hour used and 24-hour demo observations. Server settings
`CARSCANNER_USED_EXPIRE_MINUTES`, `CARSCANNER_DEMO_EXPIRE_MINUTES` and the global
expiry cap can tighten/change this policy. Source policy can always be stricter.
Successful acquisition reactivates expired offers. Failed/ambiguous pages never
extend availability. Shared catalogue URLs are excluded from individual renewal.

Exact structured offers renew current INR price and availability; card-local
sold/booked evidence retires only its matching source URL. Two consecutive 404/410
checks at least an hour apart remove an offer; errors reset that sequence.
Missing parsers are reported as inconclusive, not as available or sold.

Every scheduled pass runs lifecycle maintenance even if acquisition fails, uploads
its report, then refreshes the search projection. Reports include source/condition
counts, overdue renewal backlog, failures, recent runs and late heartbeat evidence.
Origin leases prevent simultaneous background jobs and delay retries after blocks.
The requested 15-minute free GitHub cadence was observed dispatching hours apart;
an always-on worker is required before committing to strict freshness targets.
`inventory_service` runs both workloads independently of customer requests.

## Used-model frontier

Background scans learn model families from CarDekho/CarTrade cards and national
CarWale used-model links. Discovery includes discontinued models and retains
original evidence URLs and advertised counts. Those counts are not our inventory.
`python -m src.inventory_refresh_planner --seed-observed-models` bootstraps family
jobs from stored source observations; old observations only identify what to crawl.
The daily national workflow runs this bootstrap automatically.

Regular scheduling requeues stale completed model jobs without resetting partial
or failed work. The quarter-hour worker reserves one general, one demo, three model,
three continuation and two global catalogue jobs. Use `--models-only`,
`--catalogues-only` or `--continuations-only` for bounded
operator runs. All classes retain normal claim locks, source verification and retry
fences. Audit artifacts now include `model_frontier` source/model progress.
See ADR 013 for scope and remaining city-only-source/capacity gates.

## National make sweep and audit

`National Make Coverage` runs daily at 01:35 UTC using existing GitHub Actions
secrets. It schedules all supported makes, then reserves up to 100 baseline jobs
on the reviewed CarDekho/CarWale national adapters, at three pages per job.
Regular acquisition still handles all other verified sources and continuations.
Both workflows share their concurrency group. No paid service is added.

Run `python -m src.inventory_refresh_worker --baseline-only --limit 100
--source "CarDekho Used" --source "CarWale Used"` for the same bounded recovery.
`python -m src.inventory_coverage --output coverage/national-coverage.json` audits
current used/demo results, source attribution, seller location labels and scan
status for every supported make. The daily workflow uploads this report even if
acquisition fails. A missing report fails the artifact step. Empty or single-source
coverage remains a gap to fix; neither completed traversal nor a broad make list
proves complete India-wide inventory. See ADR 012.

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
creates brand-level baseline jobs from the independent make taxonomy plus registry brands across
all eligible verified sources. It does not wait for a buyer to search that brand.
The registry's `all` capability is a matching rule, not a brand. Customer demands
retain priority within fair brand/job rotation when they overlap baseline jobs. This expands queue breadth;
it does not establish that the taxonomy contains every Indian brand or that
bounded crawls cover entire source catalogues. Size worker capacity against
queue age and each source's freshness target before claiming a coverage SLA.

ADR 011 records the starvation repair. Claims prefer the least recently attempted
brand, then unserved/older jobs within it, then demand priority. Scheduler updates
preserve queued age; successful partial scans retain their continuation. New keys
are case-normalized. The GitHub workflow runs ten jobs every 15 minutes.
For bounded recovery use `python -m src.inventory_refresh_worker --limit 6
--brand skoda --brand mahindra --brand hyundai --source "CarDekho Used"
--source "CarWale Used"` after scheduling work. This uses normal claim fencing and
verified adapter checks; it never substitutes fabricated or historical listings.

The service
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


## Durable page continuation (13 October 2026)

Background jobs save advertised next-page traversal in queue metadata after successful ingestion. A bounded batch leaves pending/visited URLs and requeues the same intent; the next worker resumes those pages. Successful batches reset the failure budget without resetting claim fencing. Failed batches retain their prior cursor for replay. `last_success_at` advances only when that traversal has no pending pages, rather than after every partial batch. This is traversal exhaustion, not proof of complete marketplace coverage.

Continuation URLs must belong to a registered endpoint host. Cyclic next links stop at visited pages. The initial increment covers ordinary HTML next links and pending endpoints; BMW/Mercedes scroll groups are supported by the subsequent increment below. Region partitions, scan generations and advertised catalogue totals remain open. No new table or public access grant is required; existing server-only queue access is retained.
## OEM scroll continuation (13 October 2026)

BMW and Mercedes background adapters now save `next_group` per endpoint inside the existing queue continuation. A later batch opens a fresh public browsing session, reads the current advertised group count and resumes from that position. The configured inventory-page budget is shared across endpoints; session bootstrap/token requests add transport overhead and are not inventory pages. Tokens and cookies are never checkpointed.

An empty response before the advertised end or missing pagination metadata during resume fails the batch, preserving its previous checkpoint. Successful ingestion precedes checkpoint advancement. A changed catalogue can shift group membership during a multi-batch scan; resumable traversal alone does not prove a snapshot-consistent or exhaustive catalogue. Scan generations, reconciliation, other source-specific APIs and real extraction/coverage audits remain open.

## Advertised city and dealer catalogues

Global both-condition jobs follow reviewed same-host city links and advertised
dealer stock catalogues, independent of buyer destination. Their existing
continuations preserve pending/visited pages and scope provenance across runs.
Coverage reports expose `catalogue_frontier` with last batch/error, discovered
scopes and advertised counts. `traversal_exhausted_unverified` means advertised
links were exhausted; it does not assert complete market coverage.

Luxury Ride uses its public filter API for pages after the first. A response
showing the wrong page is rejected, retaining the previous successful checkpoint.
See DECISIONS/014-advertised-city-dealer-traversal.md for the reviewed contract.
