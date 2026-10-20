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
  Operator-only local parser samples/replay are documented in PARSER_REPLAY.md;
  automatic capture and bounded sample retention remain unimplemented. Ledger
  retention is implemented below but not activated or operationally verified.

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

## Manual verification command

After schema inspection, the manual Controlled Scan Ledger Verification workflow
runs only on main with the existing encrypted test database credential. It shares
the acquisition scheduler concurrency group, but attributes its proof to the exact
claimed refresh ID, attempt and claim timestamp rather than a time window.
`python -m scripts.verify_scan_ledger --source "Existing source" --brand "Make"`
requires explicit process-local opt-in. It claims one existing queued job and sets
page budget one (not a universal HTTP-request count). Deferred/superseded work,
missing batches and negative-only observations fail verification. Output contains
role, batch ID and counts; no credentials or listing payloads. It does not enable
the global gate or schedule sustained writes. A successful positive write is not
proof of physical availability, source breadth or completeness.

Private tables intentionally have no RLS browser policies. The Supabase advisor's
[INFO no-policy finding](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy)
is expected; adding public policies to silence it would weaken the boundary.

## Bounded whole-generation retention

`retain_scan_ledger()` defaults to dry-run; no schedule invokes it. It inspects at
most 50 candidates (hard max 200), and permits at most 10 generations, 100 batches
and 1,000 memberships per call. Minimum age is 30 days. Both capture/latest-batch
and all batch completion/claim times must be old. Oversized generations stay
whole; reports disclose skipped reasons and cannot count rows hidden by locks.

Queue rows are locked before generation rows with SKIP LOCKED, matching workers.
Queued/running work, any current generation reference, malformed continuation,
incomplete batches and recent evidence are preserved. Failures roll back the
operation; caller-owned transactions retain commit control. Local lock/statement
timeouts bound each SQL wait. Deletes cascade audit children only, never canonical
vehicles/listings/observations, queue rows or availability. Expired audit history
cannot prove an inventory gap. Exact reclaimed disk bytes are not reported;
PostgreSQL storage reclamation depends on vacuum and is separately unmeasured.

Apply is explicit and requires an owner-authorized maintenance connection. The
runtime-access proposal grants only SELECT/INSERT/UPDATE and command-specific RLS
policies to the existing private worker role; no DELETE/TRUNCATE, browser grant,
credential or bypass. Owner approved and the exact migration was applied on 20 October. RLS remains
enabled; browser access and worker DELETE remain denied. Security advisors
returned no findings. Retention apply is not enabled by that access grant.

## Controlled operation evidence, 20 October 2026

GitHub run39277563309 attempt2/job118392295466 succeeded using the actual private
runtime role. Supabase independently confirmed batch53377108-7ad5-5e82-8584-
7f0aad9d9944 with30 accepted observations and30 positive memberships, both
completeness/absence flags false. This one-batch write proof does not establish
freshness, physical availability or source coverage. Global collection stays off;
retention remains unscheduled and parser replay remains open.
