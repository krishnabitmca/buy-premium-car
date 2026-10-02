# PostgreSQL Source Intelligence

CarScanner uses PostgreSQL/Supabase as the persistent source-intelligence control plane. It is not the customer-facing vehicle inventory cache.

## Tables
- sources — canonical source registry and lifecycle/adapter state
- source_capabilities — brand, condition, and segment capabilities
- source_endpoints — source URLs/endpoints
- source_health — health and inventory-verification observations
- source_discoveries — deep-discovery candidates and evidence

## Ownership model

config/sources.yaml is the version-controlled bootstrap/recovery seed.

When SOURCE_INTELLIGENCE_DATABASE_URL or DATABASE_URL is configured:
1. the application attempts to load the registry from PostgreSQL;
2. the database registry is authoritative for source planning;
3. YAML remains a deterministic fallback if the control-plane database is temporarily unavailable.

This fallback applies only to source metadata. It must never cause data/latest.json or another historical inventory snapshot to be returned as current customer inventory.

## Production setup

1. Apply 002_source_intelligence.sql.
2. Apply 003_source_intelligence_rls.sql.
3. Apply 004_source_discoveries_source_id_index.sql.
4. Configure SOURCE_INTELLIGENCE_DATABASE_URL or DATABASE_URL in backend/crawler environments.
5. Run scripts/bootstrap_source_intelligence.py.
6. Verify sources, capabilities, and endpoints.
7. Verify RLS and absence of customer-facing policies.
8. Verify source health/discovery writes when database connectivity is enabled.

## Lifecycle

DISCOVERED -> CLASSIFIED -> VALIDATED -> PARSER_CREATED -> INVENTORY_VERIFIED -> LIVE

Only a source with a verified live adapter is executable by customer search.

## Runtime behavior

Customer search loads source intelligence, plans sources from customer intent, executes only live adapters, fetches current external source data, validates listings, and returns source health/evidence.

The database is therefore a control plane for where/how to search, not a replacement for live marketplace responses.

## Security

Source-intelligence tables have RLS enabled. No public/authenticated customer policy grants direct access by default. Database credentials are deployment secrets.
