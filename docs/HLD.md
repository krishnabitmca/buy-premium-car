# CarScanner — High-Level System Design (HLD)

## 1. Purpose

CarScanner is a PAN-India used and demonstrator vehicle search, price-comparison, and decision-support aggregator. It discovers live vehicle listings from multiple automotive sources, normalizes them, validates identity and freshness, compares comparable vehicles, and presents evidence-backed results while preserving original source links.

CarScanner does not own inventory and does not act as the seller.

## 2. Architecture

Customer -> Web UI -> Search API

Search API -> Catalog Service
           -> Source Intelligence / Source Planner
           -> Live Marketplace Adapters
           -> Deal Intelligence

Source Intelligence / Source Planner -> PostgreSQL / Supabase
                                      -> sources
                                      -> capabilities
                                      -> endpoints
                                      -> health
                                      -> discoveries

Live adapters -> External marketplaces -> Current normalized listings

Background workers:
- Deep Source Discovery
- Daily Crawl
- Source Health Persistence
- Live Catalog Matrix
- Persona Agent
- Verification / Browser E2E

## 3. Source Intelligence Control Plane

PostgreSQL/Supabase is the persistent system of record for source intelligence when configured.

It stores the source registry, capabilities, endpoints, health observations, and deep-discovery candidates. It does NOT represent current vehicle inventory.

config/sources.yaml is the version-controlled bootstrap/recovery seed. It is not customer inventory.

Source lifecycle:

DISCOVERED -> CLASSIFIED -> VALIDATED -> PARSER_CREATED -> INVENTORY_VERIFIED -> LIVE

Only sources with a verified live adapter are executable by customer search.

## 4. Source Planner

The source planner converts customer intent into a ranked source plan using:
- brand
- model
- used/demo condition
- budget range
- destination

It uses source capabilities, segment fit, brand relevance, condition relevance, destination context, and source priority.

Destination may increase regional-source relevance but never removes India-wide sources from the inventory universe.

The planner does not fetch inventory.

## 5. Live Marketplace Layer

Source -> Fetch -> Parse -> Normalize -> Identity Validate -> Provenance -> Normalized Listing

Current configured live adapters:
- CarDekho Used
- CarWale Used
- Cars24 Luxury Used
- Spinny Luxury Used
- Motozite Demo

Candidate/discovery-only sources are not counted as effective live inventory coverage until their adapters are verified.

## 6. Search flow

Buyer search
 -> Web UI
 -> Search API
 -> load source intelligence
 -> build intent-specific source plan
 -> select only live adapters
 -> query live marketplace sources concurrently
 -> normalize responses
 -> validate identity
 -> deduplicate
 -> apply hard filters
 -> calculate market reference
 -> calculate purchase context
 -> build evidence
 -> return results + source strategy + source health + live_at

If PostgreSQL is temporarily unavailable, the source registry may fall back to YAML. This fallback is only source-control metadata; historical inventory must never be used as current customer inventory.

## 7. Data ownership

### Source intelligence control plane
- PostgreSQL/Supabase sources
- capabilities
- endpoints
- health
- discoveries

### Current inventory plane
- live external marketplace responses through verified adapters

### Historical/reporting plane
- data/latest.json
- reports
- historical observations

These planes must not be conflated.

## 8. Normalized listing model

Listing identity: brand, model, variant, identity_confidence
Vehicle: condition, manufacturing_year, mileage, fuel, transmission, body_type
Price: observed_listing_price_lakh
Location: seller_city
Source: source, source_url, original_url, extraction_method
Evidence: raw_listing_text, identity_evidence
Freshness: observed_at / live_at

Observed fields are source facts. Calculated fields are derived by CarScanner. Assumptions must be labelled.

## 9. Geography model

Destination is purchase context, not the inventory boundary. India-wide inventory remains discoverable even when the buyer is in Bengaluru and a listing is in another city/state.

## 10. Market reference

Comparable observations are grouped by brand + model + condition. Used and demonstrator observations must not be mixed. A market reference is shown only when sufficient comparable evidence exists.

## 11. Reliability

Fetch layer:
- bounded timeout
- bounded response size
- content-type validation
- bounded retries
- exponential backoff
- bounded concurrent source execution

A source outage is different from zero inventory. Partial source failure is reported independently. If all live sources are unavailable, the API returns an explicit live-source-unavailable response. Historical data must never silently become current inventory.

## 12. Security

Source-intelligence tables have Supabase RLS enabled. No public/authenticated customer policy grants direct access to these control-plane tables by default. Backend database access uses protected server-side credentials. Credentials must never be committed.

## 13. Observability

Track source fetch success, latency, HTTP errors, parser failures, inventory verification, lifecycle state, discovery confidence, promotion rate, search latency, source coverage, live-unavailable rate, and useful-result rate.

## 14. Scaling strategy

Near term:
- source intelligence PostgreSQL control plane
- live marketplace adapters
- search API
- web UI
- evidence/provenance
- automated verification

Later:
- more adapters
- persistent normalized inventory
- canonical vehicle identity
- price history
- search/index layer if measured scale requires it
- buyer accounts and alerts

Do not introduce Kafka, Elasticsearch, Kubernetes, or microservices until measured scale requires them.

## 15. Core architectural invariants

1. CarScanner is an aggregator, not a marketplace.
2. Customer search is live by default.
3. India-wide inventory is the default search universe.
4. Destination is purchase context, not an inventory restriction.
5. Historical data is never silently presented as current inventory.
6. Asking price is an observed fact, not proof of a good deal.
7. Source attribution and original listing URLs are mandatory.
8. Identity validation happens before presenting a listing as a match.
9. Source outage and zero inventory are different states.
10. PostgreSQL/Supabase is the source-intelligence system of record when configured.
11. YAML is bootstrap/recovery metadata, not customer inventory.
12. Only verified live adapters can execute in customer search.
13. Database failure must not cause a silent historical-inventory fallback.
14. Source/parser/database changes require automated verification before release.
15. Source-intelligence tables are backend control-plane data and are not directly exposed to customer API roles.

## 16. Final design principle

CarScanner's advantage should come from normalization, identity accuracy, evidence quality, source coverage intelligence, and cross-marketplace comparison — not infrastructure complexity.
