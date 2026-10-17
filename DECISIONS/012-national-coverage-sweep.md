# ADR 012 — National all-make acquisition and coverage evidence

All supported makes need active acquisition, not just a search dropdown and
queued jobs. Reserve a daily bounded national baseline sweep for the two reviewed
multi-brand marketplace adapters, alongside the existing 15-minute fair worker
across all enabled verified sources. Baseline claims exclude model and destination
demands; regular workers retain those jobs and checkpointed continuations.

The new workflow shares the acquisition concurrency group, uses existing secrets
and canonical ingestion, and fetches at most three pages per job / 100 jobs per
run. It provisions no infrastructure. It cannot establish exhaustive national
inventory or a freshness SLA. Source failures retain bounded retry behavior.

Publish a daily artifact auditing every supported make for used and demo inventory,
actual contributing sources, seller location labels, and baseline traversal state.
Reuse the customer search projection so sold, expired or disabled-source listings
cannot inflate counts. Zero means a coverage gap, never evidence of an empty market.
Location labels may include neighborhoods; their count is not a normalized city count.

Source-specific make slugs belong in reviewed source configuration.
Checkpoints retain their root routes; a reviewed route correction restarts the
old traversal after host validation, preserving idempotent ingestion.
Normalize accented make identity and search canonical aliases without rewriting historical
rows. Follow explicitly advertised aria-label next-page links as well as rel=next.
Destination remains purchase context, not an implicit geographic boundary.
