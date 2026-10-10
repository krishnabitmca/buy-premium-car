# CarScanner — Project Context

## Purpose
CarScanner is an India-wide automotive search aggregator that helps a buyer discover, compare, and evaluate premium used and demonstrator cars across cities and states.

It is not a marketplace. CarScanner does not own inventory or replace the original seller. It aggregates evidence and sends the buyer to the original listing/source.

## Current product direction
The core customer journey is intentionally simple:
1. What are you looking for? Used / Demonstrator.
2. Brand.
3. Model (optional).
4. Budget.
5. Where will you buy/register the car?

The destination city/state provides purchase context. It is not automatically an inventory boundary.

Example: a buyer in Bengaluru looking for a ₹30–40 lakh premium car should be able to discover a materially better deal in Delhi, Hyderabad, Mumbai, etc. The product should explain interstate/local implications rather than hiding the car.

## Non-negotiable product invariants
1. CarScanner is an aggregator, not a marketplace.
2. Search is India-wide by default.
3. Destination != inventory restriction.
4. An out-of-city vehicle can be a valid result.
5. Distance is decision context unless the buyer explicitly chooses a hard constraint.
6. Asking price alone is not proof of a good deal.
7. Historical data is not proof that a vehicle is currently available.
8. Preserve source attribution and original seller/listing links.
9. Evidence and confidence should be visible where they affect decisions.
10. Do not expose every internal matching criterion as a first-screen filter.
11. Expand inventory/source coverage incrementally; do not pretend PAN-India coverage exists before it does.
12. Prefer small, testable changes over broad rewrites of working systems.

## Current implementation snapshot
- GitHub: krishnabitmca/buy-premium-car
- Vercel project: buy-premium-car
- Front end: index.html
- Search API: api/search.py
- Deal intent engine: src/deal_engine.py
- Persistent inventory: Postgres vehicles/listings/observations; data/latest.json is a legacy report
- Source configuration/crawlers: config/, src/
- Supabase schema: supabase/migrations/001_deal_watch.sql
- Daily crawl workflow: .github/workflows/daily-crawl.yml
- Daily and continuous acquisition: src/main.py and src/inventory_service.py; both use canonical ingestion
- Watch inventory reads: scripts/process_alerts.py, through src/inventory_db.py, with no flat-file fallback

The current front end has been redesigned around the India-wide search journey and calls /api/search.

## How future work should begin
Before changing behavior or architecture, read:
1. PROJECT_CONTEXT.md
2. PRODUCT.md
3. ARCHITECTURE.md
4. ROADMAP.md
5. CHANGELOG.md
6. relevant files under DECISIONS/

Then inspect the current implementation before proposing a replacement.

## Safe evolution rule
Do not redesign the whole system because one new feature is requested. First identify the smallest layer that should change:
- UX change -> front end
- search behavior -> /api/search.py
- deal evaluation -> src/deal_engine.py
- source/inventory coverage -> crawler/config/data pipeline
- persistence/alerts -> Supabase/API
- architecture change -> document a decision first

Every meaningful architectural or product change should update the relevant decision/documentation and changelog.

## Deployment truth
Never claim a production deployment unless it has been verified. A GitHub merge and a Vercel deployment are separate states.

## Long-term direction
CarScanner should evolve through these layers:
Search -> Coverage -> Evidence -> Deal intelligence -> Buyer/interstate intelligence -> Scale

PAN-India scale is a destination, not a prerequisite for every increment.
