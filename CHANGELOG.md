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
