# CarScanner Changelog

## 2026-10-08

- Restore live dealer inventory from Big Boy Toyz, AutoBest Emperio, Luxury Ride and 9th Gear with card-specific price, mileage, photo and original-link extraction; exclude sold, reserved and zero-price cards.
- Route Big Boy Toyz and Motozite used searches to brand/model inventory rather than generic home pages.
- Remove Motozite's implicit demo-only parser filter; the adapter applies the customer's condition after extracting card-local evidence.

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
