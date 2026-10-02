# CarScanner Test Strategy

## Purpose

CarScanner is certified only when the customer journey works end-to-end. A green unit-test suite is not sufficient evidence that the deployed website is usable.

## Test layers

1. **Unit / component tests**
   - Source planning and applicability
   - Marketplace adapters and parsers
   - Normalization and deduplication
   - Filtering and scoring
   - Inventory freshness
   - Source health / circuit breaker

2. **API contract tests**
   - Catalog
   - Brand/model catalog dependency
   - Search request/response contract
   - Validation and error handling
   - Source isolation
   - Inventory/live coverage fallback

3. **Browser / UI tests**
   - Page load and JavaScript execution
   - Brand dropdown population
   - Model dropdown population after brand selection
   - Search submission
   - Every visible filter
   - Filter combinations
   - Sorting
   - Clear All
   - Zero-result state
   - Error states

4. **Production smoke tests**
   - Deployed homepage
   - /api/catalog
   - /api/catalog?brand=<brand>
   - Search journeys against the deployed environment
   - Critical source coverage

## Release gates

### P0 — Must pass

- Homepage loads.
- Brand dropdown loads.
- Model dropdown loads after brand selection.
- Search can be submitted.
- Used / Demo / Used+Demo work.
- Price validation works.
- Clear All works.
- No customer-visible JavaScript error blocks search.

### P1 — Must pass

- Fuel, age, city and sort filters.
- All Models behavior.
- Interstate search with destination city.
- Source failure isolation.
- Zero-result handling.
- Deduplication and live-source verification.

### P2

- Secondary refinements and market intelligence presentation.

## Status vocabulary

- PASS: Executed and expected behavior verified.
- FAIL: Executed and observed behavior contradicts expected behavior.
- BLOCKED: Could not execute because a prerequisite is broken.
- NOT TESTED: Scenario has not yet been executed.
- NOT APPLICABLE: Scenario does not apply to the release.

A deployment marked READY by Vercel is not equivalent to a CarScanner release PASS.

## Required evidence

Every release report must record:

- Git commit SHA
- Vercel deployment ID and URL
- Test execution timestamp
- Scenario ID
- Expected result
- Actual result
- PASS/FAIL/BLOCKED/NOT TESTED
- Defect reference where applicable
