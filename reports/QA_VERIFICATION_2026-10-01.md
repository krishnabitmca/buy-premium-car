# CarScanner QA Verification Report — 2026-10-01

## Scope

QA reviewed the current main commit `6e0a0f3` against the CarScanner canonical journey:

> Bengaluru buyer → Used/Demo → premium brand/model → ₹30–40L → India-wide inventory → compare live evidence → seller city/interstate context → original listing.

The goal was adversarial verification: break assumptions, exercise negative paths, and identify where the current system can mislead the customer.

## Coverage model

Coverage is reported separately because test *design* and test *execution* are not the same thing.

| Layer | Planned cases in QA branch | Executed in this environment |
|---|---:|---:|
| Parser/unit-style | 11 | Not executed |
| HTTP/API contract | 7 | Not executed |
| Browser/E2E scenarios | 1 suite covering 15+ assertions | Not executed |
| Existing smoke tests | 2 | Previously passed; not re-executed on current branch |
| Total automated cases/suites | 21+ | 2 previously executed |

The new suite therefore raises **test-design coverage substantially**, but it must not be reported as execution coverage until CI/preview execution succeeds.

## Functional coverage against the UAT catalogue

The existing QA/UAT catalogue contains 29 functional E2E scenarios, 10 market-intelligence scenarios, 12 API scenarios, 10 negative/resilience scenarios, 6 security scenarios, browser/responsive scenarios, performance scenarios and deployment scenarios.

Current automation explicitly exercises representative paths across:
- live catalogue
- dependent models
- budget validation
- destination-is-not-a-filter
- source degradation
- market median
- insufficient evidence
- no offline fallback
- seller city filtering
- price filtering
- fuel filtering
- clear filters
- sorting
- natural-language budget extraction
- market view
- evidence modal
- original source link
- empty result state

**Estimated automated requirement coverage: 21 / 77 core catalogue scenarios ≈ 27%.**

This is requirement/test-scenario coverage, not code coverage.

## Defects found

### P0/P1 — Condition selector is not enforced end-to-end

The UI sends `condition`, but `api/search.py` does not use it in matching. Used-only and Demonstrator-only can therefore return mixed inventory.

### P1 — Core live fields are not extracted

The live parser currently extracts only a limited identity/price/source set. It does not reliably populate:
- seller location
- seller city/state
- model year
- mileage
- fuel
- transmission
- body type

These fields are required by customer-facing filters and purchase context.

### P1 — Interstate purchase context is therefore unreliable

Without seller location/state, the acquisition layer commonly falls back to `location_unknown`, undermining the core India-wide/interstate use case.

### P1 — Demonstrator records are currently normalized as Used

Parsed live rows are assigned `condition_signal="used"`. Demonstrator discovery therefore cannot be trusted.

### P1 — Market intelligence is only as good as live extraction

The median calculation is deliberately conservative, but incomplete extraction can leave too few comparable observations even when source pages visibly contain inventory.

### P2 — Acquisition-cost field is misleading

`estimated_total_lakh` is currently the listing price for local/same-state cases, not a true all-in acquisition estimate.

## Release gate

Do not call the build functionally verified until:
1. Condition filtering passes Used / Demo / Both.
2. Live parser extracts the fields required by the UI.
3. Seller city/state and interstate context are verified with real source observations.
4. At least one demonstrator source path is verified.
5. Full API + browser E2E suite executes successfully.
6. A working Vercel preview is browser-tested with no console/runtime errors.
7. No stale/offline inventory appears after source failure.

## QA principle

A green smoke test is not enough. E2E testing is intended to validate the full integrated user workflow, while integration tests focus on interactions and data flow between components. Coverage should therefore be tracked by both requirement scenarios and executed tests, not by a single percentage.