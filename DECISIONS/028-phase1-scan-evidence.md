# ADR 028 — Phase 1 scope and fail-closed scan evidence

Status: accepted from the owner's 19 October mandate; initial contract implemented.

Phase 1 includes all-brand used/demo acquisition, freshness, accurate search and
operability. Preserve canonical PostgreSQL, queues, adapters and claim fencing.
The [execution plan](../docs/PHASE1_EXECUTION.md) records independent reviews.

Separate successful batch execution, frontier exhaustion and verified completeness.
Successful traversal evidence has a versioned generation ID, start time, scoped
configuration fingerprint and terminal reason. Continuations retain identity;
changed parser/scope configuration restarts from current roots. Legacy checkpoints
remain resumable, labelled legacy, without completeness authority. Metadata uses
the existing fenced ingestion/checkpoint transaction.

No current adapter proves exhaustive enumeration. Every outcome explicitly has
completeness_verified=false and absence_reconciliation_permitted=false. Missing
next links, advertised counts, completed jobs and one matching offer per source
cannot establish complete coverage. Public indexed search remains inventory_partial
and reports source presence separately. No additional request-time crawling.

Queue last_success_at retains execution meaning, not complete-scan evidence.
The latest successful batch is not an immutable scan ledger. Failed attempts do
not replace or renew it. Explicit sold evidence and ordinary expiry remain intact;
absence removes no listing.

Durable membership, retained parser evidence and authoritative enumeration remain
next dependencies. No verified-complete constructor is offered by this first
contract. A later reviewed source may authorize scoped missing-offer rechecks,
never blanket sold status. See plan for tradeoffs and acceptance.
