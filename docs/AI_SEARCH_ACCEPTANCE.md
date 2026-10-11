# CarScanner AI search acceptance contract

Product-owner direction: an AI-era search engine for used and demonstrator cars,
with lightning-fast results and the broadest discoverable options across India.
All brands are in scope; BMW and Mercedes are examples, not preferred coverage.

## Experience to deliver

A buyer can describe a need in ordinary language or use simple controls. Search
returns useful indexed cars immediately, then supports refinements and comparison.
AI translates intent, retrieves alternatives and explains trade-offs using actual
listing evidence. It never generates inventory, prices, ownership facts or seller
claims. The buyer can inspect original offers and their observation times.

Continuous discovery and acquisition maintain the index independently of traffic.
Missing or stale coverage triggers background work; it does not make every buyer
wait for every marketplace. New results may appear after refresh with explicit
observation times. Historical reports are never substituted for current inventory.

## Engineering acceptance gates

| Requirement | Evidence needed before declaring it delivered |
|---|---|
| Fast search | Target warm API p95 ≤500 ms and first usable browser results p95 ≤1 second on a documented India test network and agreed concurrency/dataset. These are engineering targets, not measured achievements. Report cold starts and slow tails separately. |
| No crawler dependency | Block external marketplace hosts in an end-to-end test: indexed search, filtering, sorting and pagination still work; a missing match schedules background refresh. |
| Every brand | Independent canonical taxonomy, including aliases and models; test every supported brand with source-backed results or an explicit coverage gap. The taxonomy must not depend solely on already-entered dealer capabilities. |
| Broad source discovery | Every applicable known source has an explained coverage state. Measure newly discovered sources and adapter validation; a registry live flag alone cannot prove a successful current scan. |
| Deep inventory acquisition | Persist traversal progress by source/brand/region and resume across batches. Track scan generations, pages, advertised totals where available and completion. Small free batches must not continually revisit the same first pages. |
| Freshness | Show actual observation time; process price updates and explicit sold evidence. Test expiry, retries, source outages and recovery without reviving older available/cheaper observations. |
| Full-result refinements | Fuel, mileage, age, condition, budget, location preference and sort apply to the entire indexed match set, not just the first loaded cards. Pagination preserves the intent and ranking. |
| AI intent | Test varied wording, aliases, misspellings, budgets and compound constraints across brands. Extract typed constraints, show interpreted intent and let buyers correct it. Ambiguity must not silently invent constraints. |
| Grounded retrieval | AI recommendations reference returned listing IDs and evidence; hard constraints are enforced by the backend. Semantic retrieval may suggest alternatives but cannot silently relax those constraints. |
| Lowest price and best option | Keep distinct: cheapest observed comparable offer versus the strongest evidence-backed option. Validate same-car grouping against real cross-source examples; retain ambiguous identities separately. |
| Responsive web/mobile | Verify first results, refinements, comparison, seller handoff, loading/failure states and accessibility on mobile and desktop. Both clients use one search contract. |
| Free testing | Preserve the current free test setup and dry-run alerts. Measure throughput/queue age before declaring national freshness; no paid AI or infrastructure commitment is implied. |

## Current implementation verdict — 11 October 2026

- **Speed: improved, target not achieved.** A local server connected to the existing Supabase Free project measured 20 sequential warm API searches: median 361.77 ms, p95 561.13 ms, with a 2046.01 ms first request. This is not a load test or first-usable-browser latency benchmark. Earlier real samples were approximately 3.4–4.2 seconds.
- **Non-blocking acquisition: partial implementation.** Configured PostgreSQL searches now default to index-only responses, including empty/partial results, and record demand for background work. Operators can explicitly enable legacy live fallback; database-disabled deployments retain the legacy path. Source metadata is snapshotted per request with a maximum 15-second reuse window; inventory is queried afresh. Connection pooling and one count/page SQL snapshot reduce round trips.
- **All-brand acquisition: incomplete.** The app exposes 16 registry-derived
  brands; seven returned zero observations in the real audit. Baseline scheduling
  now covers those registered brands, but queueing is not completed acquisition.
- **Source depth: incomplete.** Adapters have bounded page budgets without durable
  continuation. Full source-plan display exposes gaps; it does not fill them.
- **AI: not delivered.** `index.html`'s `runAssistant` uses string/regex rules and
  catalog lookups. It is not validated AI intent interpretation or semantic search.
- **Full-inventory refinements: incomplete.** Browser filters and market summaries
  currently operate on loaded observations. More pages can change visible options.
- **Evidence/comparison: foundation only.** Canonical observations, source offers
  and comparable cohorts exist; physical-car matching and deal accuracy need real
  cross-source validation.
- **Production: not verified.** The existing hosted site returns HTTP 402. Passing
  unit/database/browser tests on the branch does not validate hosted operation.

## Implementation order

1. Establish reproducible latency/coverage benchmarks; remove request-time crawl
   dependence from the target search contract. Measure metadata round trips,
   connection setup and inventory-query plans before choosing optimizations.
2. Deliver resumable all-brand/source/region acquisition and coverage/freshness
   manifests. Repair missing adapters by measured coverage impact.
3. Move all search constraints and ranking to the indexed backend, maintaining
   source attribution, observation times and deterministic pagination.
4. Add a bounded AI intent/retrieval layer with schema validation and grounded
   explanations. Keep simple searches fast and useful if AI is slow/unavailable;
   explanations may enrich the results after they appear.
5. Run the complete acceptance matrix and representative load tests, then verify
   cloud scheduling, responsive/mobile behavior and deployment.

See ADR 008 for the target architecture and the distinction between this contract
and runtime behavior that is still being migrated.
