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
