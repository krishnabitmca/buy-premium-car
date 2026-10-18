# 017: Fair source validation and conservative city evidence

The source-expansion job probes only five candidates every three hours. Taking
the first five registered candidates each time permanently starves later
dealer/OEM candidates and can entirely exclude open-web discoveries.

Choose the least recently attempted candidates within registered and web pools.
Unattempted candidates precede retries. Reserve the first slot of every five
for web discoveries and lend empty-pool capacity to the other pool. This also
gives web discoveries a turn when a manual run has a one-slot budget. Duplicate
URLs retain registered metadata. Confidence filtering remains in force.

Persist attempt start, result and fencing token on source_discoveries. Preserve
discovered_at as historical evidence. Atomic claims exclude running attempts
for thirty minutes; a new token fences late completion after recovery. Staged
validated/promoted discoveries wait for adapter review. New endpoints on an
existing source remain inactive until reviewed; rediscovery never disables an
already active endpoint. This does not automatically create live inventory.

Publish incremental per-run JSON evidence so interruptions remain visible.
Existing workflow concurrency and five-probe budget remain. Finite recurring
candidate pools rotate; an unbounded influx of new candidates can delay retries.
Dispatch delays and public-source blocking still prevent a completeness SLA.

The configured query bank has 512 queries before demand enrichment, with four
search backends. Limit each run to six queries, rotating the window by the
three-hour UTC time slot. Preserve other discover() callers' default behavior.
Missed scheduler windows are not replayed or counted as observed coverage, and
changing demand can change the bank. This bounds work, not elapsed-time or
full-bank completion guarantees.

Add a private city rollup using recognized city labels, known aliases and an
optional matching state suffix. Preserve every raw seller label in the sparse
matrix. Ambiguous regions, addresses, conflicting states and absent labels stay
unresolved. Keep distinct cities such as Mumbai and Navi Mumbai separate.
Deduplicate canonical vehicle identities within each city/source/condition row;
these rows are not additive national vehicle totals. Buyer search geography and
purchase-context inference remain unchanged.

These changes unblock acquisition and measurement. They do not establish an
independent market denominator, OEM partnerships, or near-complete demo stock.
