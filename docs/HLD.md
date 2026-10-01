# CarScanner — High-Level System Design (HLD)

## 1. Purpose

CarScanner is a PAN-India used and demonstrator vehicle search, price-comparison, and decision-support aggregator.

The system discovers live vehicle listings from multiple automotive marketplaces and seller sources, normalizes them into a common vehicle/listing model, validates identity and freshness, compares comparable vehicles, and presents evidence-backed results while preserving the original source link.

CarScanner does not own inventory and does not act as the seller.

## 2. Architecture

Customer / Buyer
        |
        v
Web UI / Mobile Web
        |
        v
Search API
        |
        +-------------------+--------------------+
        |                   |                    |
        v                   v                    v
Catalog Service      Live Marketplace      Deal Intelligence
                     Search Layer
        |                   |                    |
        +-------------------+--------------------+
                            |
                            v
                 Normalized Vehicle/Listing
                            |
                            v
                  Identity + Evidence Layer
                            |
                            v
                    Source Adapters
          +---------+--------+--------+---------+
          |         |        |        |         |
       CarDekho  CarWale  Cars24   Spinny   Motozite
          |         |        |        |         |
          +---------+--------+--------+---------+
                            |
                            v
                 External Marketplaces

Background acquisition and QA:
GitHub Actions -> Daily Crawl
               -> Live Catalog Matrix
               -> Persona Agent
               -> Verification / Browser E2E

Future persistence:
Normalized Listings + Vehicle Identity + Price History + Source Health
                         |
                         v
                 PostgreSQL / Supabase
                         |
                         v
                   Search Index
                (only when scale requires)

## 3. Major components

### Web UI
Current implementation: index.html

Collects lightweight customer intent:
- Used / Demonstrator
- Brand
- Model
- Budget
- Destination
- Optional refinements

Displays live status, vehicle results, market/reference information, evidence, and the original marketplace link.

The UI remains thin. Business rules belong in the API/domain layer.

### Catalog Service
Current implementation: api/catalog.py and src/live_marketplaces.py

Responsibilities:
- source-backed brands
- source-backed current models
- brand alias normalization
- model URL validation
- rejection of dealer/offers/view-all pages
- rejection of discontinued/upcoming/estimated catalog entries
- removal of source price/status metadata
- model deduplication

A model in the dropdown means it has passed current source-catalog validation. It does not mean a used listing currently exists.

### Live Marketplace Layer
Current implementation: src/live_marketplaces.py

Each marketplace is an adapter with a common contract:

Source -> Fetch -> Parse -> Normalize -> Identity Validate -> Provenance -> Normalized Listing

Current sources:
- CarDekho Used
- CarWale Used
- Cars24 Luxury Used
- Spinny Luxury Used
- Motozite Demo

### Search API
Current implementation: api/search.py

Responsibilities:
- validate customer intent
- query live sources
- apply hard constraints
- calculate purchase context
- calculate market/reference information
- assemble evidence
- return per-source health and live observation time

### Deal Intelligence
Current implementation: src/deal_engine.py

Uses observed price, comparable market observations, age, mileage, variant, condition, source corroboration, evidence quality, price history, seller/source quality, and location/acquisition context.

A derived deal signal is never presented as a guaranteed final transaction price.

## 4. Normalized listing model

Listing
  identity
    brand
    model
    variant
    identity_confidence
  vehicle
    condition
    manufacturing_year
    mileage
    fuel
    transmission
    body_type
  price
    observed_listing_price_lakh
  location
    seller_city
  source
    source
    source_url
    original_url
    extraction_method
  evidence
    raw_listing_text
    identity_evidence
  freshness
    observed_at / live_at

Observed fields are facts extracted from a source.
Calculated fields are derived by CarScanner.
Assumptions must be explicitly labelled.

## 5. Identity and deduplication

Requested identity
      |
      v
Brand/model query parsing
      |
      v
Independent listing identity extraction
      |
      +-- brand mismatch --> reject
      |
      v
Model mismatch --> reject
      |
      v
Canonical URL
      |
      v
Duplicate detection
      |
      v
Identity confidence + evidence
      |
      v
Comparable listing

The requested query must never be injected into a listing to make it appear to match.

## 6. Search flow

Buyer search
  -> Web UI
  -> Search API
  -> resolve brand/model
  -> query live marketplace sources
  -> normalize responses
  -> validate identity
  -> deduplicate
  -> apply hard filters
  -> calculate market reference
  -> calculate purchase context
  -> build evidence
  -> return results + source health + live_at
  -> Web UI

## 7. Geography model

Destination is purchase context, not the inventory boundary.

Example:

Customer destination: Bengaluru

PAN-India inventory:
- Bengaluru
- Mumbai
- Delhi
- Hyderabad
- Pune
- other cities

The system can compare price, evidence, freshness, distance, and acquisition implications. A potentially relevant interstate listing must remain discoverable.

## 8. Market reference

Comparable observations are grouped by brand + model + condition.

Used and demonstrator observations must not be mixed into one market reference.

Market reference should only be shown when sufficient comparable evidence exists.

## 9. Source reliability

Each source has independent health:

CarDekho -> LIVE -> valid results
CarWale  -> LIVE -> valid results
Cars24   -> UNAVAILABLE

A source outage must not erase valid results from other sources.

Zero inventory is different from source outage.

If all live sources are unavailable, the API returns an explicit live-source-unavailable response.

Historical data must never silently become current customer inventory.

## 10. Historical inventory

data/latest.json and reports are useful for:
- reporting
- development
- regression testing
- price-history analysis
- operational analysis

They are not the customer-facing source of current inventory.

Historical observations must carry explicit observation timestamps/status.

## 11. Reliability

Fetch layer:
- bounded timeout
- bounded response size
- content-type validation
- bounded retries
- exponential backoff

Retryable HTTP errors:
408, 425, 429, 500, 502, 503, 504

Other important failure rules:
- empty response is source failure, not zero inventory
- wrong brand/model is rejected
- tracking parameters are removed before deduplication
- partial source failure is reported independently

## 12. Security

- Validate and bound customer input.
- Never execute untrusted marketplace content.
- Preserve external URLs as navigation only.
- Limit response sizes and retries.
- Future customer accounts/watchlists should minimize stored personal data.

## 13. Observability

Source metrics:
- fetch success rate
- fetch latency
- HTTP errors
- parser failures
- listings discovered/rejected
- source availability

Identity metrics:
- brand rejection rate
- model rejection rate
- identity confidence
- duplicate rate

Search metrics:
- search latency
- zero-result rate
- source coverage
- live-unavailable rate
- results per search

Product metrics:
- original listing click-through
- cross-city engagement
- search-to-useful-result rate

## 14. Scaling strategy

Phase 1:
- live marketplace adapters
- source-backed catalog
- search API
- web UI
- evidence/provenance
- automated CI

Phase 2:
- additional sources
- stronger canonical vehicle identity
- persistent normalized inventory
- price history
- better deduplication

Phase 3:
- search/index layer
- distributed acquisition workers
- source rate limiting
- coverage dashboards

Phase 4:
- buyer accounts
- saved searches
- price-drop/deal alerts
- personalized deal intelligence

Phase 5:
- interstate landed-cost intelligence
- registration/transfer intelligence
- richer vehicle history
- seller/dealer quality signals

Do not introduce Kafka, Elasticsearch, Kubernetes, or microservices until measured scale requires them.

## 15. Recommended target architecture

Near-term CarScanner should remain a modular monolith with independently testable source adapters.

Web Client
   |
Search API
   |
   +-- Catalog Domain
   +-- Search Domain
   +-- Deal Intelligence
   |
Normalized Vehicle/Listing Domain
   |
   +-- Source Adapters
   |      +-- CarDekho
   |      +-- CarWale
   |      +-- Cars24
   |      +-- Spinny
   |      +-- Motozite
   |
   +-- Persistent Store
          +-- Listings
          +-- Vehicle Identity
          +-- Source Observations
          +-- Price History
          +-- Source Health

Background workers:
- Daily Crawl
- Catalog Matrix
- Persona Agent
- Verification / Browser E2E

This keeps the architecture simple enough to operate today while preserving clean boundaries for future scale.

## 16. Core architectural invariants

1. CarScanner is an aggregator, not a marketplace.
2. Customer search is live by default.
3. India-wide inventory is the default search universe.
4. Destination is purchase context, not an inventory restriction.
5. Out-of-city listings remain discoverable.
6. Distance is a decision factor unless explicitly made a hard filter.
7. Historical data is never silently presented as current inventory.
8. Asking price is an observed fact, not proof of a good deal.
9. Source attribution and original listing URLs are mandatory.
10. Identity validation happens before presenting a listing as a match.
11. Source outage and zero inventory are different states.
12. UI remains thin; domain rules belong in backend/domain layers.
13. Architecture scales incrementally based on measured need.
14. Major source/parser changes require automated verification before release.

## 17. Final design principle

CarScanner's architectural advantage should come from normalization, identity accuracy, evidence quality, and cross-marketplace comparison — not infrastructure complexity.

The system should make adding the next marketplace possible without changing the customer search experience.
