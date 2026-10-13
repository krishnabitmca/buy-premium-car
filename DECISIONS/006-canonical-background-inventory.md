# ADR 006 — Background acquisition and watches use canonical Postgres inventory

## Status

Accepted for the database migration requested by the product owner.

## Decision

The production daily acquisition command and continuous refresh service use the
same verified source adapters, persistent refresh queue and canonical
vehicle/listing/observation tables in PostgreSQL. Customer watch processing reads
those tables through the same latest-observation and expiry rules as inventory
search. Missing database configuration or database failure must fail the command;
neither SQLite nor repository JSON is a fallback for alerts or acquisition.

The former broad browser crawler remains available only as an explicit legacy
reporting tool. Its outputs are diagnostic artifacts, not production inventory.
Optional JSON exports are derived from Postgres and uploaded as workflow artifacts
rather than committed to main as an application database.

Source discovery remains a separate scheduled process that persists candidates
and validates them before adapter verification. Unverified candidates cannot enter
customer inventory simply because their pages contain plausible prices.

## Consequences

- Production ingestion has one canonical write path, and alerts see updated prices
  and explicit sold observations without waiting for a repository snapshot.
- Alert reads are paginated and database-required; the optional web inventory
  feature flag cannot silently disable background watch processing.
- Watch budgets are converted from lakhs to rupees at the deal-engine boundary;
  make/model, explicit condition, mileage and ownership constraints are enforced.
- Any-match alerts can notify a verified budget/criteria match without pretending
  it is a bargain. Good/exceptional or target-discount alerts still need price
  comparison evidence. Unknown evidence cannot satisfy a hard constraint.
- Provider delivery, watch ownership verification, heartbeat leases and national
  coverage measurement remain separate launch gates.

ADR 005's request-time live search remains unchanged by this increment. The
inventory search path is the persistent projection shared with watches.
