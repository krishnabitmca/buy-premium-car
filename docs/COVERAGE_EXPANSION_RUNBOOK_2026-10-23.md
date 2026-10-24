# Source coverage: efficient database diagnosis and release gates

## Incident, 23 October 2026
A read-only diagnostic joined `sources`, `listings`, and `vehicle_observations`
by source before counting distinct listing and observation IDs. PostgreSQL
returned SQLSTATE 53100 (temporary file: no space left on device). A separate
`count(*)` of listings succeeded (13,537), and `pg_database_size` reported
89 MB. This does **not** prove permanent database storage exhaustion. The
many-to-many join can multiply rows per source and create excessive temporary
sort/hash work. Do not repeat this diagnostic or increase ingestion concurrency
until the query plan and free temporary disk are checked.

## Bounded, nonmultiplying diagnostic
Run in a read-only session with a short timeout. Aggregate each child table
independently and only then join to sources. The counts are *stored history*,
not customer-search eligibility.

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL work_mem = '4MB';
WITH listing_counts AS MATERIALIZED (
  SELECT source_id, count(*) AS listings FROM public.listings GROUP BY source_id
), observation_counts AS MATERIALIZED (
  SELECT source_id, count(*) AS observations, max(observed_at) AS latest_observed
  FROM public.vehicle_observations GROUP BY source_id
)
SELECT s.name, coalesce(l.listings,0) AS listings,
       coalesce(o.observations,0) AS observations, o.latest_observed
FROM public.sources s
LEFT JOIN listing_counts l ON l.source_id=s.source_id
LEFT JOIN observation_counts o ON o.source_id=s.source_id
ORDER BY s.name;
ROLLBACK;
```

For the release gate, reuse the *actual customer search eligibility query*,
not a raw count. Report: eligible unique listings, source contributors, share
of top three sources, recent refresh success, used/demo breakdown, valid images
and source URLs, and brand/model/price filter E2E pass rates. A 403 or a partial
scan must never retire inventory or be interpreted as zero supply.

## Expansion order
1. Verify the recently persisted Motozite, Quikr and AutoHangar listings appear
   in customer search with usable links and images; verify refresh reliability.
2. Repair existing BMW OEM eligible inventory and demo semantics.
3. Certify Spinny, Audi Approved Plus and Volvo Selekt one at a time against
   permitted source interfaces. Keep zero-evidence sources non-contributing.
4. Expand regional dealer/OEM feeds with source-specific evidence and dedupe.
5. Do not merge stale conflicting PRs #29, #33 or #38 without rebasing and tests.

Do not treat a source registered in YAML or a parser fixture as coverage.
