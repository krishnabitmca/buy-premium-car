# CarScanner Architecture

## Architectural principle
Keep the product layered so inventory acquisition, search, deal intelligence, presentation, and future buyer services can evolve independently.

## Current layers

### 1. Source acquisition
Located primarily under:
- src/
- config/
- .github/workflows/

Responsibilities:
- discover listings
- normalize source data
- retain source identity
- capture listing URLs
- capture timestamps/freshness
- produce inventory snapshots

The crawler should collect broadly. Customer constraints should generally be applied at search/match time.

### 2. Inventory data
Current repository snapshot:
- data/latest.json
- historical data under data/ and reports/

Inventory records should retain enough provenance to answer:
- where did this vehicle come from?
- when was it observed?
- what identity information was available?
- what evidence supports the result?

### 3. Search API
api/search.py

Responsibilities:
- accept customer search intent
- search across available inventory
- apply hard constraints
- calculate purchase context
- rank/present useful results
- return source/evidence information

Destination should annotate local/same-state/interstate context rather than silently restricting the inventory universe.

### 4. Deal intelligence
src/deal_engine.py

The generic deal engine provides concepts including:
- DealIntent
- ListingSnapshot
- DealEvaluation
- GenericDealEngine

This layer should remain reusable and should not become tightly coupled to a particular UI.

### 5. Presentation
Current primary UI:
- index.html

The UI should remain thin: collect intent, explain results, expose evidence, and link to original sources. Business rules should not proliferate in client-side code when they belong in the API/domain layer.

### 6. Persistence and future alerts
Supabase schema exists under:
- supabase/migrations/001_deal_watch.sql

Future customer-specific watch/alert functionality should build on explicit deal intent rather than duplicating search rules.

## Data contract principles
When adding fields:
- prefer additive changes
- preserve existing fields unless there is a strong reason to remove them
- preserve source URLs
- preserve source timestamps
- distinguish observed facts from calculated fields
- document breaking changes

## Search contract
The search contract should support at least:
- condition
- brand
- model
- budget range
- destination
- optional refinements

The contract should remain extensible for:
- mileage
- age
- fuel
- transmission
- ownership
- radius
- seller type
- must-have/nice-to-have/avoid

Not every field should be exposed in the first screen.

## Scaling path
1. Repository-backed inventory
2. More source adapters
3. Normalized canonical vehicle identity
4. Better deduplication
5. Persistent inventory store
6. Search/index layer if needed
7. Deal/evidence scoring
8. Buyer-specific intent and alerts
9. Interstate landed-cost intelligence
10. PAN-India operational scale

Do not introduce distributed infrastructure merely because the long-term system may need it.

## Reliability principles
- A crawl failure must not be confused with zero inventory.
- Historical observations must remain distinguishable from current availability.
- Source outages should be observable.
- Search should degrade gracefully when one source is unavailable.
- Production behavior should be verifiable independently of GitHub merge state.
