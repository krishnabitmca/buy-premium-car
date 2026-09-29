# CarScanner Changelog

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
