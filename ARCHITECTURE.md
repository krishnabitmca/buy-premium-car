# CarScanner Architecture

## Architectural principle
Keep source discovery, source governance, live inventory acquisition, search, deal intelligence, presentation, and future buyer services independently testable.

## 1. Source discovery and intelligence

Implemented in src/discovery.py, src/source_intelligence.py, src/source_registry_db.py, config/sources.yaml, PostgreSQL/Supabase migrations, and crawler workflows.

Responsibilities:
- discover source candidates
- classify source type, condition, segment, geography, and brand coverage
- persist discovery evidence
- maintain source lifecycle state
- maintain capabilities and endpoints
- record source health
- produce an intent-specific source plan

PostgreSQL/Supabase is the production source-intelligence system of record when configured. config/sources.yaml is the versioned bootstrap/recovery seed.

## 2. Live marketplace search

Customer search queries live marketplace pages/APIs through adapters whose adapter_status is live. data/latest.json is historical/reporting data and must never be used as a customer-facing inventory fallback.

## 3. Data planes

Source intelligence:
- PostgreSQL/Supabase registry, capabilities, endpoints, health, discoveries

Current inventory:
- live responses from external marketplaces

Historical/reporting:
- data/latest.json, data/, reports/

A source-intelligence row is source metadata, not a vehicle listing.

## 4. Search API

api/search.py loads source intelligence, plans sources, queries live adapters, applies hard constraints, calculates purchase context, and returns source/evidence information.

Destination annotates local/same-state/interstate context rather than silently restricting inventory.

## 5. Source lifecycle

DISCOVERED -> CLASSIFIED -> VALIDATED -> PARSER_CREATED -> INVENTORY_VERIFIED -> LIVE

Only LIVE adapter sources enter customer search execution.

## 6. Reliability

- A source fetch failure is not zero inventory.
- Source outages are observable and persistable.
- One slow source must not serially block all other sources.
- PostgreSQL control-plane failure may use YAML source metadata fallback.
- PostgreSQL failure must never trigger historical inventory fallback.
- Production behavior must be verified independently of GitHub merge state.

## 7. Security model

RLS is enabled on sources, source_capabilities, source_endpoints, source_health, and source_discoveries. No direct customer API policy is granted by default. Database credentials remain deployment secrets.

## 8. Scaling path

1. Live source adapters
2. Source intelligence PostgreSQL control plane
3. More source adapters
4. Canonical vehicle identity
5. Persistent normalized inventory
6. Better deduplication
7. Search/index layer if needed
8. Deal/evidence scoring
9. Buyer-specific intent and alerts
10. PAN-India operational scale

Do not introduce distributed infrastructure merely because the long-term system may need it.
