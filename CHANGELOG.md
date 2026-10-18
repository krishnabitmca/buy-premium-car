## 2026-10-18 — Continuous discovery, renewal and expiry lifecycle

- Run Docker HTTP traffic through pinned Gunicorn/WSGI with bounded concurrency,
  worker-local pools, private access logs and configured graceful request drain.
- Add a separate canonical-database readiness probe and verify actual Linux
  request handling, in-flight SIGTERM drain and production-adapter browser flows.
  Keep paid activation and national latency/availability claims gated separately.

- Preserve operator disables, adapter state, parser overrides, removed capabilities
  and inactive endpoints during routine registry bootstrap. Require explicit
  reviewed rollout for replacement/activation of existing source configuration.
- Explain excluded inventory using named canonical customer-eligibility checks.
  Report per-source queue counts/ages, including disabled sources, without treating
  elapsed queue age as proof of worker failure or summing overlapping reasons.

- Add Škoda Certified Pre-Owned public stock API acquisition and resumable page
  positions; keep session tokens ephemeral and manufacture year/mileage unknown
  when the card does not establish them.
- Add Fusion Cars advertised brand catalogues, priced individual cards, explicit
  sold-card evidence and conservative individual listing renewal for both feeds.
- Add explicit live stock/detail rollout verification. These are used sources;
  neither unregistered status nor the OEM programme establishes demo condition.

- Rotate source probes by durable last-attempt evidence; reserve web-discovery
  capacity, recover interrupted probes and fence stale completions. Publish
  per-run evidence. Stage new endpoints inactive until adapter review.
- Bound background web discovery to six rotating queries per run, leaving
  capacity for validation instead of exhausting the full query bank first.
- Add canonical city/state coverage rollups while retaining raw seller labels,
  unresolved location evidence and India-wide search behavior.

- Add operational source/location/brand/model/condition coverage cells, declared
  scope progress, source repair priorities and explicit worker-capacity scenarios.
  Publish JSON/Markdown artifacts without inventing market coverage percentages.
- Share offer eligibility with search; measure extraction yield with per-batch
  pages rather than cumulative traversal pages. Preserve raw location evidence.
- Reserve catalogue/model/continuation capacity in standalone workers, isolate
  bucket failures, lend unused renewal slots and avoid enrolling unknown-condition
  inventory into condition-specific renewal work.

- Publish expiry-policy metadata into a versioned Elasticsearch v2 index with
  explicit strict mappings. Existing scoped create-index permissions suffice;
  no mapping-management privilege or deletion of the v1 index is required.

- Coalesce rapid refinement edits for 250ms; explicit Search remains immediate
  and cancels queued work. Changing brand cancels a pending reset/refinement scan.

- Serve observed model names independently of live catalogue latency and enrich
  them in a bounded background task. Historical model metadata never establishes
  current listing availability.

- Bound the API database pool at eight connections by default, allow a ten-second
  checkout wait, and increase pending HTTP sockets for parallel browser bursts.
  Client disconnects do not trigger a second search error response; server errors
  record exception types without buyer input or credentials.
- Use transaction pooling for Supabase shared-pooler runtime URLs on port 5432,
  preserving the host, role and database and disabling prepared statements. An
  explicit session-mode override remains available for session-dependent tooling.

- Add private durable per-listing renewal, domain leases and worker heartbeat
  records; preserve history and fence all canonical writes against stale claims.
- Reserve demo catalogue acquisition and used/demo renewal capacity independently
  from large discovery queues. Apply bounded retries, cooldowns and crash recovery.
- Renew exact structured listing offers, retire card-local sold/booked inventory,
  and require two spaced disappearance checks; errors never establish sold status.
- Share source-aware 48-hour used / 24-hour demo expiry across customer search,
  watches, maintenance and derived index validity. Successful observations restore
  expired offers; no history is deleted.
- Upload lifecycle/backlog evidence every scheduled run and report heartbeat gaps.
  Free scheduled dispatch delays remain a production freshness SLA limitation.

## 2026-10-17 — Advertised city and dealer catalogue acquisition

- Traverse reviewed marketplace city links and full dealer catalogues with
  durable breadth-first checkpoints and reserved quarter-hour worker capacity.
- Parse Luxury Ride's full stock cards, compound crore/lakh prices and stable
  listing IDs; use its public filter API to follow actual catalogue pagination.
- Reject stalled dealer pagination and positive-stock pages with no extracted
  cards. Preserve failed-batch checkpoints for retries.
- Report scopes, visited/pending pages, advertised counts and last errors without
  treating traversal exhaustion as proof of complete India-wide inventory.
- Keep acquisition independent of buyer destination; no UI or paid infrastructure
  changes.
- Use hashable equality on required brand/model cohort keys to avoid quadratic
  comparison work as inventory grows; preserve null-safe optional variant/year.
- Verify same-repository PR customer journeys against the branch's local server
  using approved test inventory; keep post-merge checks on the deployed release.

## 2026-10-17 — Source-evidenced used-model acquisition

- Discover used/discontinued model families from source cards and used-model links;
  retain provenance and advertised counts as acquisition evidence, never stock proof.
- Fan out durable national model jobs across reviewed verified adapters, preserve
  checkpoints on rediscovery and reschedule completed work by source freshness.
- Reserve model and continuation capacity within the existing ten-job refresh budget.
- Add verified CarTrade card extraction and extend operational model-progress reports.
- No presentation/UI changes or paid infrastructure added.

## 2026-10-17 — National all-make acquisition and coverage audit

- Add a daily bounded national baseline sweep alongside the fair 15-minute worker,
  so model/location demand cannot consume its reserved all-make acquisition slots.
- Audit every supported make for used/demo eligible results, contributing sources,
  seller location labels and traversal status; upload the report on crawler failure too.
- Correct accented make identity, canonical alias search, source-specific make slugs
  and aria-label next-page traversal. Preserve original listing provenance and
  India-wide search regardless of registration destination.
- Reuse successful public model metadata for 15 minutes with bounded storage and
  synchronized loads; prices and availability never enter this cache.
- Preserve the selected make when the initial catalogue arrives late, and ignore
  out-of-order model responses after a buyer changes makes.
- Coverage reports explicitly retain gaps; these changes do not claim exhaustive
  marketplace coverage or guaranteed inventory for every make/condition.

## 2026-10-17 — Repair mainstream-make acquisition gaps

- Recognize and schedule the independent make taxonomy even when registry brand capabilities are incomplete.
- Rotate worker service across brands/jobs; preserve queued age and normalize new intent keys so high-priority continuations cannot indefinitely starve other makes.
- Run bounded background refresh every 15 minutes and support focused verified-source recovery.
- Show retained search criteria and provide an explicit brand-only retry action. Classify empty partial inventory as a coverage gap.
- A bounded real recovery indexed 52 Skoda, 53 Mahindra and 55 Hyundai observations from CarDekho and CarWale; Honda's unrestricted used search returned 801. These counts do not establish complete marketplace coverage.

## 2026-10-17 — Verified Gemini free-tier pilot

- Recheck the live search release and verify whole-index fuel/mileage constraints and global ordering.
- Verify real Gemini interpretation of compound buyer preferences, explicit unsupported-criteria disclosure, and browser review before indexed search.
- Enable the approved Gemini 3.8 Flash pilot in Render and ignored local configuration with the existing durable 30-call daily cap; no billing or paid fallback.
- Preserve ordinary search and provider-failure handling. This pilot does not establish national source completeness or general model accuracy.

## 2026-10-16 — Authoritative buyer search and guarded Gemini pilot

- Apply typed refinements and deterministic ordering across PostgreSQL inventory before pagination; browser refinements requery the index.
- Keep comparison cohorts independent of buyer budget/refinements and expose full filtered-index counts/cities/sources.
- Retain explicit adapter body style and show observed offers, provenance and purchase-context caveats in an accessible evidence dialog.
- Add all-make taxonomy selection and improve mobile result ordering and control sizes.
- Add optional consent/review-based Gemini interpretation with durable server-only quota capped at 30/day. Keep buyer AI disabled: live synthetic generation returned provider high-demand errors.
- Record remaining coverage, grounded explanations, shortlist/watch, mobile and capacity gates in docs/BUYER_EXPERIENCE_REQUIREMENTS.md.

## 2026-10-16 — Optional Elasticsearch trial integration

- Add nested-offer search with complete generation publication and separate scoped runtime/indexer credentials.
- Fence derived results with a transactional PostgreSQL revision, canonical offer hydration and expiry checks; fall back on changes, partial responses, provider failure or trial expiry.
- Refresh the projection after hourly background acquisition and expose the actual search engine in API responses. Keep PostgreSQL comparison calculations and source provenance.
- Document cross-region latency, full-refresh/write-serialization limits and the unapproved paid continuation in ADR 009. This change does not claim national capacity or broader source coverage.

## 2026-10-13 — Render release verification

- Release to the existing free Render service with indexed PostgreSQL search and dry-run alerts.
- Expose only the valid public release commit at /api/version and wait for that commit before push-triggered hosted checks, avoiding tests against a rolling deployment.
- Test the customer POST indexed-search contract instead of crawl-heavy legacy GET; wait for the completed market render in the adversarial UI check.

## 2026-10-13 — Search timing and optional shared cache

- Add request-isolated Server-Timing stages and reproducible mixed-query/concurrency and exact-query EXPLAIN scripts.
- Add optional Redis-backed public source metadata reuse with bounded TTL/size, remaining-life-aware local reuse, short operation timeouts and outage fallback. Listing prices and availability remain fresh PostgreSQL reads.
- Materialize comparison cohorts after a real plan showed repeated aggregate execution. Sampled BMW server execution improved from 90.576 to 22.146 ms; API p95 remains above target.
- Add disposable Redis CI coverage for cross-process reads, expiry/corruption recovery and fresh price/source-disable behavior. Document the implementation and remaining performance gates in docs/SEARCH_PERFORMANCE.md.

## 2026-10-13 — OEM scroll continuation

- Resume BMW and Mercedes public inventory scroll groups across background batches, sharing the configured page budget across endpoints.
- Save endpoint/group positions after ingestion; obtain fresh session tokens on every invocation without persisting tokens in queue metadata.
- Fail a resumed traversal when pagination metadata disappears or an advertised group returns empty content; retain its prior checkpoint for retry.
- Verify both OEM transports across successive batches and Mercedes transport → persisted queue → canonical ingestion → indexed HTTP search against disposable PostgreSQL. Marketplace completeness and live catalogue accuracy remain separate validation gates.
- Local validation: 1,034 unit tests and 31 PostgreSQL integration tests pass.

## 2026-10-13 — Durable HTML page traversal

- Persist pending/visited pages on background refresh jobs and resume after bounded batches; checkpoint only after ingestion succeeds.
- Requeue partial traversal, retain progress on failure, and preserve claim fencing across batches. Retry budgets count failures since the last successful batch.
- Advance scan freshness only after pending traversal is exhausted; this does not establish catalogue completeness. OEM scroll/API continuation remains outstanding.

## 2026-10-11 — Fast indexed search foundation

- Default configured PostgreSQL searches to index-only responses; preserve explicit legacy fallback opt-in and background demand recording.
- Reuse bounded PostgreSQL connections, isolate each caller transaction, and snapshot source metadata per request with at most 15 seconds of metadata reuse. Listing prices, availability and observation times remain fresh database reads.
- Retrieve total and paginated inventory in one SQL snapshot, including empty/out-of-range pages and deterministic ordering.
- Verify rollback, broken-connection recovery, request isolation, cache expiry, configuration changes and pagination. Local validation: 1,029 unit tests and 28 PostgreSQL integration tests pass.
- Measure 20 sequential warm Supabase-backed searches: median 361.77 ms, p95 561.13 ms; first request 2046.01 ms. The 500 ms p95 target and national-load acceptance remain open.

## 2026-10-10 — Canonical daily acquisition and watch matching

- Route the production daily command through the same Postgres refresh pipeline as the continuous worker; keep broad browser/SQLite reports under an explicit legacy command.
- Read paginated current inventory for watches with no JSON fallback or dependency on the web inventory flag. Keep optional exports as diagnostic workflow artifacts instead of committing a file database to main.
- Correct lakh/rupee budgets and make/model keys; enforce explicit condition, mileage, owners, current evidence and target discount. “Any” alerts accept valid criteria matches without inventing bargain evidence.
- Preserve source stock IDs and price basis, adopt existing URL offers when canonical identity matches, and calculate current comparison cohorts before watch pagination/budget filtering.
- Skip inactive users, unconsented/disabled channels and mismatched notification frequencies; use price-version event identities so rescans do not resend and qualifying price changes may notify.
- Document pending ownership, outbox recovery, RLS, national coverage and deployment gates in ADR 006 and continuous inventory operations.

## 2026-10-10 — Continuous database refresh service

- Add a continuous scheduler/worker command that requires PostgreSQL and remains separate from HTTP search.
- Preserve full source parser/endpoint configuration and claim jobs immediately before execution; isolate failures within a batch.
- Recover abandoned claims, retry failed work with bounded backoff, and fence completion by attempt number.
- Schedule freshness per source/intent successful scan, including zero-result scans, rather than the newest listing across the whole source.
- Document operational behavior and outstanding PAN-India launch gates in docs/CONTINUOUS_INVENTORY.md.

## 2026-10-10 — Inventory reliability foundation

- Correct the refresh workflow database variable and fail background commands when database configuration is absent; serialize queue metadata for psycopg JSONB writes.
- Select the actual latest listing observation before checking budget/availability, with an observation-ID tie-breaker. Earlier prices and available observations cannot be resurrected by filtering history.
- Record explicit sold evidence for existing offers transactionally; failed fetches and missing catalogue rows do not imply a sale.
- Normalize inventory UUIDs, numeric values and timezone-aware timestamps for the existing numeric-lakh JSON contract; preserve offer-level observation times and accept the inventory condition projection in API filtering.
- Add a disposable-local-Postgres CI job covering migrated schema, scheduling, claiming, ingestion and real HTTP search responses. Coverage manifests, worker leases, identity fixes and alert ownership/matching remain subsequent reliability work.

## 2026-10-08 — Scheduled source monitoring

- Register additional demo marketplace, authorised-dealer and OEM inventory leads as candidates, including Porsche Finder, Skoda Certified, GetOnRoadPrice, DiscountedCarsIndia, Motodeals and Gurudev Skoda; point Volvo Selekt at its inventory portal.
- Daily crawling now visits active configured inventory endpoints as well as primary URLs.
- Three-hour source expansion explicitly rechecks registered candidates alongside open-web discoveries. Deduplicate by URL, preserve distinct same-domain inventory surfaces, skip disabled sources and verified live URLs.
- Successful validation stages candidate adapters; empty/sold, blocked and enquiry-only pages cannot automatically become live search inventory.

## 2026-10-08 — Additional dealer demo coverage

- Added Sundaram Motors active dealer cards, advertised pagination (maximum ten pages), explicit demo asking prices and per-page failure diagnostics.
- Added Gurudev Tata's public current demo-stock API. Keep unknown mileage unknown, omit catalogue photos, and label the published Chennai on-road price.
- Added Big Boy Toyz's dedicated demo collection alongside its brand inventory; deduplicate overlapping vehicle links.
- Preserve exact model, budget and condition filtering. Separate on-road price observations from unspecified-price comparable groups.

# CarScanner Changelog

## 2026-10-18 — Worker-local API overload protection

- Bound WSGI API execution to two concurrent handlers per worker; excess work
  receives a retryable, no-store 503 before body reads.
- Preserve health/static/version/preflight access and release capacity after
  handler or response failures. Verify concurrent rejection and recovery.
- Retry read-only browser requests within existing deadlines; return selectable
  brand taxonomy immediately while one bounded metadata refresh runs in background.
- Keep paid upgrades disabled at the owner's request; this is not a national
  capacity or distributed abuse-control claim.


## 2026-10-11 — AI search acceptance standard

- Record the product-wide speed, all-brand/source acquisition, grounded AI and full-inventory refinement requirements in docs/AI_SEARCH_ACCEPTANCE.md.
- Define indexed search with background acquisition as the target in ADR 008; preserve source evidence and explicitly distinguish target architecture from incomplete runtime migration.
- Align the core product promise with this target. No AI model, paid provider or production deployment is implied by this documentation change.

## 2026-10-11 — Brand-independent coverage baseline

- Schedule each registered brand across all eligible verified sources without requiring prior customer demand; preserve India-wide scope and queue deduplication.
- Return the complete search source plan and expose per-source coverage gaps in the browser. Loaded observations are not proof of source catalogue completeness.
- Record the remaining taxonomy, durable continuation, source adapter and coverage-matrix launch requirements in ADR 007.

## 2026-10-11 — Multi-source BMW and Mercedes coverage

- Restore missing runtime parser/template settings for all existing registry rows while preserving lifecycle and operator overrides; scheduled refreshes repeat the idempotent repair.
- Add source-scoped CarDekho, CarWale and Cars24 card extraction with individual URLs, years, mileage and asking prices; exclude navigation, EMI, explicit sold cards and unrelated domains.
- Follow advertised same-source result pages and public BMW/Mercedes scroll groups with bounded page budgets. Include Big Boy Toyz's ordinary collection alongside its demo inventory.
- Correct partial-inventory pagination and add a load-more control. Preserve database comparison cohorts across API pages instead of recomputing a reference from one page.
- Snapshot brand identity once per request/scan with thread-local context instead of loading the registry for every listing; refresh the snapshot on the next request.
- Nationwide completeness remains unverified: budgets bound scans, some adapters still extract no inventory, and the hosted deployment remains blocked.

## 2026-10-11 — End-to-end preview repairs

- Restore missing reviewed source parser, catalog and endpoint configuration with an explicit dry-run-first command that preserves existing lifecycle, operator settings and access controls.
- Match whole model identity tokens in stored inventory, including dealer trim names; expose per-source match counts.
- Correct stored-observation wording throughout results and details, show actual observation timestamps, and bound frontend search waits.
- Respect model and explicit budget/year in assistant searches; clear all search controls and keep market summaries aligned with visible filters.
- Verify real dealer acquisition into Supabase and the local customer journey in desktop/mobile browsers. Nationwide coverage and hosted production verification remain separate gates.

## 2026-10-08

- Restore live dealer inventory from Big Boy Toyz, AutoBest Emperio, Luxury Ride and 9th Gear with card-specific price, mileage, photo and original-link extraction; exclude sold, reserved and zero-price cards.
- Route Big Boy Toyz and Motozite used searches to brand/model inventory rather than generic home pages.
- Remove Motozite's implicit demo-only parser filter; the adapter applies the customer's condition after extracting card-local evidence.
- Read Big Boy Toyz's explicit product demonstrator/stock flags and model-family catalog from public embedded JSON; correlate only visible card IDs and reject contradictory family assignments.
- Reuse adapter identity matching in the API's final filter so hyphenated model names do not discard validated cross-source results and model substrings cannot create false matches.

- Acquire Mercedes OEM inventory through the public session-token/inventory request used by its showroom UI.
- Parse individual OEM article cards with explicit condition, asking price, specifications, images, city, and seller link; enable the verified adapter.


- Reject catalogue/category pages in generic vehicle extraction; require individual vehicle identity and price plus year/mileage or VIN.
- Correct escaped regexes in generic detail extraction so real price/year/mileage evidence is read.
- Read parser strategy from PostgreSQL source metadata as well as YAML fields.
- Distinguish fetched sources from sources with matching listings in the UI; empty searches no longer imply market-wide absence.


## 2026-09-29

### Live search foundation
- Replaced the customer search dependency on data/latest.json with a live marketplace query path.
- Added live CarDekho-backed brand/model catalog discovery.
- Added live marketplace adapters for CarDekho, CarWale, Cars24 and Spinny.
- Fixed the UI/API GET-vs-POST mismatch that prevented the redesigned search experience from loading correctly.
- Added explicit live-source status and observation timestamps.
- Prevented silent fallback to stale/offline inventory when live search fails.
- Fixed Used vs Demonstrator condition matching.



## 2026-09-29

### Product foundation
- Established persistent project context documentation.
- Formalized CarScanner as an India-wide automotive search aggregator rather than a marketplace.
- Formalized the rule that destination/registration location is purchase context, not an automatic inventory restriction.
- Documented incremental PAN-India scaling strategy.
- Documented architecture boundaries and safe-change workflow.

### Search experience
- Redesigned the primary customer journey around a small set of high-value inputs.
- Added India-wide search messaging.
- Moved refinements after the initial search.
- Added result explanations around market context, evidence, source count, and purchase context.

## 2026-09-28

### Existing product state
- Current inventory snapshot contains a small set of premium used vehicles from multiple sources/cities.
- Search API supports query, destination, budget, and age-related behavior.
- Deal intent engine and Supabase deal-watch schema are present.
## 2026-10-10 — Free testing setup

- Add a local preview launcher with ignored server credentials, complete watch routing, catalog preflight and a health endpoint; restrict static serving to the customer page.
- Respect disabled request-time crawling even for empty inventory, accept partial inventory responses in the UI and label database observations accurately.
- Configure hourly batches of 10 jobs, three pages per source, five discovery candidates and dry-run alerts with separate encrypted free-test credentials.
- Enable queue RLS, add a dedicated backend runtime role and explicitly grant server watch/sequence access without storing passwords in migrations.
- Document the existing Supabase free project setup and the approval required to activate scheduled changes on main.
