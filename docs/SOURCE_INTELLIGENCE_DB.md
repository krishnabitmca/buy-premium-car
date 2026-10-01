# PostgreSQL Source Intelligence

CarScanner now supports PostgreSQL as the persistent system of record for source intelligence. config/sources.yaml remains the versioned bootstrap seed so local development and recovery remain deterministic.

## Production setup

The repository already has a Supabase/PostgreSQL integration for Deal Watches, so the same PostgreSQL project can host this schema.

1. Apply supabase/migrations/002_source_intelligence.sql.
2. Configure SOURCE_INTELLIGENCE_DATABASE_URL (or DATABASE_URL) in the crawler/API environment.
3. Run python scripts/bootstrap_source_intelligence.py.
4. Verify public.sources contains the configured registry.
5. The crawler records deep-discovery candidates and source health when the database is configured.

## Safety

A candidate source is never executed by customer live search. Discovery does not silently promote a source. PostgreSQL is the source-intelligence control plane, not the inventory cache. Credentials must never be committed to Git.

Lifecycle:
DISCOVERED -> CLASSIFIED -> VALIDATED -> PARSER_CREATED -> INVENTORY_VERIFIED -> LIVE

Only LIVE adapters enter customer search execution.
