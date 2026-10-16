# Buyer experience implementation requirements

Derived from the 16 October 2026 product review. The product goal is an
India-wide search aggregator with transparent acquisition coverage, authoritative
buyer constraints and useful source-backed comparison. AI fluency does not
establish marketplace completeness, availability, inspection or fair value.

## First implementation increment

| Requirement | Implementation | Verification |
|---|---|---|
| One authoritative intent | `src/search_intent.py`; form and generated intent use the same validator | Invalid/NaN/out-of-range inputs rejected; public round-trip |
| Whole-index constraints | PostgreSQL fuel, transmission, body style, mileage, owners, exact year, age, explicit seller city and budget before grouping/pagination | Real 65-vehicle fixture finds petrol inventory after the original first 50; two sorted pages remain disjoint |
| Global ordering | SQL recommended/price/gap/mileage/year ordering with deterministic ties | Full-index page tests; browser request contract |
| Stable comparison evidence | Cohorts calculated before buyer refinements | Narrow-budget result retains broader same-variant/year reference |
| Honest counts and provenance | Full filtered-index totals/cities/sources; distinct source count separate from offer count; original offer links/times in dossier | SQL totals; browser evidence dialogue |
| All-make selection | Existing India make taxonomy supplements discovered catalog metadata | Taxonomy is selection support, explicitly not inventory coverage |
| Optional generative interpretation | Server-side Gemini, explicit consent, review before execution, unsupported criteria and clarifications | Mock provider validation/failure tests; live generation gate remains blocked below |
| Persistent pilot quota | Atomic PostgreSQL usage reservation, hard maximum 30/day UTC, failed calls count, no prompt storage | Concurrent 15-request test admits exactly configured 5; RLS/grant checks |
| Usable mobile and keyboard evidence | Results precede long filters on mobile; larger AI control/text; modal labels, focus containment, Escape and return focus | Browser desktop/mobile verification |

The Elasticsearch v1 trial projection does not implement these new filters,
summary aggregation or relevance ordering. Such requests correctly use PostgreSQL
and report the actual backend. A wider taxonomy cannot manufacture absent cars.
Unknown source attributes fail closed under a hard constraint, which can reduce
results. Body style is retained when explicitly supplied by an adapter; this
increment does not infer it from brand/model names.

## Gemini pilot gate

Owner approved `carscanner-free-test` in the existing **Free tier** Default Gemini
Project, local ignored `.env` and Render storage only, with no billing enabled.
Model-list authentication succeeded. Synthetic generation returned provider 503
UNAVAILABLE/high demand for Gemini 3.8 Flash and 3.1 Flash Lite. A legacy 2.5 Flash
Lite attempt returned 404. These are not successful interpretation tests.

Keep `CARSCANNER_AI_ENABLED=false` until a synthetic compound-preference test and
the full consent → interpretation → review → indexed search journey succeed.
Ordinary search must continue during provider failure. No automatic provider
retry, paid fallback, web-grounding tool or private document upload is enabled.
The UI states Google's free-tier product-improvement use before consent.

## Remaining product and national-scale gates

| Priority | Requirement | Acceptance evidence required |
|---|---|---|
| P0 | More verified marketplace/OEM/dealer coverage across brands and regions | Per-source catalogue traversal/freshness and brand/city coverage measurements; partial/failing scans remain visible |
| P0 | Listing evidence completeness | Source-backed fuel/transmission/body/condition attributes, negative/sold evidence, duplicate identity validation |
| P1 | Grounded AI explanations and buyer questions | Server-retrieved public dossier, cited evidence IDs, no unsupported valuation/inspection claims, factuality evaluation |
| P1 | Shortlist, compare, saved search and controlled watch delivery | Persisted buyer choice, fresh offer revalidation, consent/preferences, successful delivery pilot; existing alerts remain dry-run |
| P1 | Shareable searches and resilient mobile application shell | URL intent restoration, accessibility tests, network recovery; separate PWA/native decision |
| P1 | Destination purchase assistance | Explicit transport/tax assumptions and current authoritative sources; estimates separated from asking prices |
| P1 | Product analytics and user evaluation | Privacy-conscious funnel/latency/coverage metrics and real buyer task success |
| P2 | Incremental search projection and national capacity | Outbox/change handling, projected filter/cohort parity, cursor pagination, load/latency SLOs, regional placement and measured infrastructure costs |

These remain requirements, not delivered claims. Do not announce a PAN-India
launch, complete source coverage or a successful generative pilot from fixture
tests alone. Record production commit and live evidence at release time.
