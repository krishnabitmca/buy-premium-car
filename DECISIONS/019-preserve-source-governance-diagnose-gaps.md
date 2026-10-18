# 019: Preserve source governance and explain inventory exclusions

Routine registry bootstrap previously replaced lifecycle state and parser metadata,
reactivated endpoints and reintroduced seed capabilities. An operator's emergency
disable or reviewed removal could therefore disappear after maintenance.

Default `sync_registry` now inserts missing sources and their initial capabilities
and root endpoint. For an existing source it only updates last-seen time and fills
missing metadata keys; database values win. It never re-enables a source or endpoint,
changes adapter state or re-adds capabilities on an existing source. Creation uses
`ON CONFLICT DO NOTHING RETURNING`, so concurrent bootstraps cannot both treat an
existing source as newly inserted. An explicit `reviewed_update=True` retains the
administrative activation contract. Only the stock/detail-verified rollout command
uses it; ordinary discovery and bootstrap do not.

Private coverage reports name the failed checks from the same predicates used by
customer inventory search. An excluded offer can fail multiple checks; reason
counts are non-additive. Missing observations fail closed. Latest observations,
source state and freshness are read in the report's repeatable-read snapshot.
No new eligibility rule, inventory fallback or public database access is added.

Show queued/running counts and oldest request/claim ages per source, including
disabled sources for diagnosis. An old queued request can reflect origin pacing,
cooldown or dispatch delay; it is not automatically a stuck worker. Disabled
sources carry an explicit do-not-schedule action. Reports do not mutate queues.

These changes make acquisition gaps actionable. They do not establish complete
catalogue snapshots, automatic absence reconciliation, national recall or a hosted
worker SLA. Partial or failed traversal remains insufficient evidence of a sale.
