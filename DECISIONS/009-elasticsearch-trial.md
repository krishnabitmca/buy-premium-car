# ADR 009 — Optional Elasticsearch trial

Status: accepted trial integration; user approved a 14-day Elastic Cloud
trial. Paid continuation is not approved.

Keep PostgreSQL authoritative. Elasticsearch holds a derived public inventory
projection, with nested asking-price offers. No customer/watch data or database
credentials enter the index. Separate 14-day API keys restrict runtime to reads
and the background indexer to read/write/create-index within `carscanner-*`.

A database statement trigger advances a transactional revision whenever vehicles,
listings, observations or sources change. The indexer reads one repeatable-read
snapshot, writes an immutable generation, waits for searchable bulk writes, then
publishes its manifest. Failed batches cannot publish partial generations.
Hourly GitHub acquisition refreshes the projection after its worker batch.

Search reads the manifest, checks revision in a repeatable-read PostgreSQL
transaction, retrieves indexed candidates/counts, and hydrates current offers and
comparison evidence from that same database snapshot. A changed revision, expired
listing, changed expiry policy, new calendar year, partial Elasticsearch response,
provider outage or expired trial/key falls back to PostgreSQL. Generations expire
within two hours, or sooner at the first offer expiry. Requests never crawl or
load a historical flat-file fallback.

This is a correctness-first trial integration. It is not yet the final national
scale design: the global revision serializes ingestion writes; full generation
refresh is hourly; canonical cohort calculations still run in PostgreSQL; and
deep pagination uses the existing bounded offset contract. Incremental outbox
publication, partitioned revisions, cursor pagination and projected cohort
evidence need later measurement/design. Do not claim a speedup without comparing
real latency. The current trial region (North Virginia) differs from Render
(Singapore), so network latency may outweigh retrieval gains at this inventory size.

Equal-price ties can use indexed generation observation ordering; prices, typed
filters, exact totals and provenance remain authoritative. Destination remains
purchase context, never a hidden search boundary.

## Initial measured rollout

The real trial passed 24 comparisons across six brands, budgets, condition and
pagination. Local-to-cloud median was 2,891.58 ms for Elasticsearch plus canonical
hydration versus 815.35 ms for PostgreSQL alone. These are a small read-only
sample, not load-capacity results. Keep normal customer requests on PostgreSQL;
the deployed POST API accepts `search_engine: "elasticsearch"` for an explicit
trial request and returns the engine actually used. Credentials remain server
side. Promote the default only after co-located measurements and removal of the
remaining evidence-query bottleneck demonstrate an improvement.
