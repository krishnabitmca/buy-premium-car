# Search performance and shared metadata cache

## Implemented

The POST search endpoint emits a `Server-Timing` header with registry loading,
source planning, pool acquisition, database execute round trip, inventory handling,
serialization and total response-preparation time. Stages overlap: do not sum
inventory and its database/pool sub-stages. Database execute time includes network
and driver work; it is not PostgreSQL server execution time. Total excludes final
socket delivery and browser rendering. Timings contain no query text or credentials.

The optional Redis-compatible cache shares public source metadata across processes.
Set server-only `CARSCANNER_REDIS_URL` to enable it; otherwise existing local caching
continues. Use `rediss://` for remote TLS connections and avoid URL query overrides.
The client has a bounded eight-connection pool, 150 ms connect/operation timeouts,
no automatic retries and a 30-second failure cooldown. Timeouts bound individual
operations, not the entire request or DNS resolution. Cache failure falls back to
the existing PostgreSQL/seed metadata path. No browser credentials or user/watch
records enter this cache.

Metadata entries have at most 15 seconds Redis TTL and a 512 KB payload limit.
Local reuse of a shared hit is limited to its remaining lifetime; it does not
renew the 15-second window. Entries are namespaced by database identity and source
config revision, using a hash so connection credentials are not present in keys.
Local cache refreshes coalesce within a process; distributed request coalescing is
not implemented. Metadata edits can remain visible for the bounded cache window.

**Inventory results, prices, availability and comparison evidence are not cached.**
The search SQL still enforces current source enablement, latest observation,
sold status and expiry on every request. Response `Cache-Control: no-store` remains.
Listing-result caching needs an ingestion/version/invalidation contract before it
can be enabled safely.

The comparison-cohort CTE is explicitly materialized. The sampled previous BMW
plan repeatedly recalculated it in a nested loop; materialization retains the
existing cohort semantics while computing this intermediate result once.

## Reproducible checks

```
python scripts/benchmark_search.py --samples 24 --concurrency 1 --output benchmark.json
python scripts/benchmark_search.py --samples 24 --concurrency 4 --output concurrent.json
python scripts/profile_inventory.py --output query-plans.json
```

The profiler reads the ignored local environment and runs EXPLAIN ANALYZE on the
same inventory SELECT for BMW, Audi and all brands. It is a developer command;
customer request input cannot enable query-plan output. Read profiling executes
the query and consumes database resources. Use controlled samples on test data.

Benchmarks use a mixed brand/zero-result workload against one configured server,
report first request separately and retain per-request stages. They are closed-loop
samples, not a national offered-load capacity test. Compare under the same network,
dataset, ingestion activity, process count and warm/cold conditions. Keep slow tails
and failures rather than reporting only cache hits.

## Measurements on 13 October 2026

Local Python server to existing Supabase Free project; 24 samples per run:

| Run | Median | p95 | Notes |
|---|---:|---:|---|
| Instrumented initial, sequential | 371 ms | 542 ms | Before cohort materialization |
| Instrumented initial, four workers | 692 ms | 1,052 ms | Before cohort materialization |
| Materialized, sequential with parallel outage smoke | 499 ms | 2,255 ms | Confounded; retained to expose variability |
| Materialized, isolated sequential | 371 ms | 719 ms | Faster sampled SQL did not establish faster API p95 |
| Materialized, four workers | 681 ms | 1,179 ms | Throughput 5.4 requests/second in this small closed-loop run |

The sampled BMW PostgreSQL execution changed from 90.576 ms to 22.146 ms; Audi
from 1.377 to 1.316 ms; all-brand from 68.556 to 58.556 ms. These are individual
plans, not server-execution p95 measurements. API execute round trips were much
larger and variable. The 500 ms API p95 target remains unmet. Redis is optional
and was not deployed locally; these runs do not measure a Redis speedup.

## Redis verification and next engine decision

CI starts a disposable Redis service and verifies cross-process cache reads,
expiry, malformed payload recovery, bounded TTL and fresh inventory price/source
checks while metadata is cached. Local tests verify outage fallback, failure
cooldown, request isolation and unchanged metadata lifetime. No shared service is
provisioned by adding this optional integration.

Elasticsearch is not installed or selected. The current measurements justify
fixing a concrete PostgreSQL plan and making latency observable; they do not yet
establish a need for another index. Next compare an optimized current-inventory
read model against Elasticsearch at representative inventory size and load,
including unique queries, ingestion, freshness correctness, facets and relevance.
Region/network placement and database variability must be measured alongside
engine execution. National coverage acquisition remains a separate requirement.
