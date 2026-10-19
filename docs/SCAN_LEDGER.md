# Private scan-write ledger

The gated worker path records successful accepted scan batches inside the existing
post-fetch claim-fenced transaction. Three private tables hold generations,
batches and accepted observation membership. None is a customer inventory index.

`prepare_batch(job, source_id, evidence, conn)` validates background contract v1,
UUIDs, source/scoped fingerprint, aware timestamps, typed page counts, explicit
false completeness/absence flags and terminal state. It reserves a deterministic
batch ID from refresh ID, claim attempt and claim start. An already completed
duplicate is detected before ingestion; conflicting/incomplete reuse fails closed.

`finish_batch(batch, accepted, evidence, continuation, conn)` checks unchanged
generation evidence and continuation identity, writes exact accepted IDs, records
counts and advances generation state. It cannot regress exhaustion to partial.
The caller owns commit/rollback. No helper commits or invokes network services.

The worker holds its existing queue claim fence before either helper. It collects
actual inserted IDs from positive ingestion and explicit catalogue negatives, then
writes membership and checkpoint on the same connection. Exceptions roll back
these writes. Failed-job bookkeeping occurs separately as before. Source discovery
enqueue outside this fence is not part of the guarantee.

## Meaning and limits

- Positive membership means an accepted write, not current eligibility or physical
  availability. Rejected parser rows are not inferred as accepted inventory.
- Multiple observations for one listing remain separate. Composite foreign keys
  bind batch/generation/queue/source and membership/observation/listing/source.
- Missing next links and completed queue jobs never establish source completeness.
  Hard database checks deny both completeness and absence-retirement authority.
- Legacy resumed generations may predate ledger capture. Earlier membership is
  unknown; no current-inventory backfill invents its history.
- No raw HTTP response, session token, price payload or buyer data is retained here.
  Parser replay samples and privacy-aware bounded retention are not implemented.

## Controlled rollout

1. Keep CARSCANNER_SCAN_LEDGER_ENABLED=false (default). Review migration and run
   real disposable PostgreSQL tests, including browser-role denial and failures.
2. Apply the CLI-generated migration through the approved deployment process.
   Existing-table identity indexes add write/storage overhead; lock and statement
   timeouts bound the migration. Failure must abort/retry after inspection, not
   disable safeguards. Do not claim zero-downtime DDL without measuring it.
3. Verify table/constraint/index definitions, RLS, effective server-role access and
   security advisors. No browser grants or additional credentials are required.
4. Run an explicitly bounded controlled acquisition with the gate true and verify
   canonical observations, membership and continuation atomically. Keep production
   gate off until this evidence exists; failed tests do not count as activation.
5. Implement and test inactive-generation retention and safe reporting before
   sustained collection. Preserve active continuation evidence. Ledger FKs may
   intentionally block deleting referenced observations until ledger retention
   is handled. Do not delete inventory to resolve an audit-retention dependency.

Rollback: disable the gate; old count-only ingestion remains supported. Additive
tables may stay private while fixes are prepared. No destructive down migration.
P1-02 closure still needs replay, retention and operational acceptance. The ledger
does not increase source breadth, independently validate cars or accelerate search.
