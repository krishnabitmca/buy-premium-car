# CarScanner continuation checkpoint

Updated 20 October 2026, morning IST. Read AGENTS.md, CARSCANNER_PROFILE.md,
CURRENT_STATE.md and required product/architecture/decision documents first.

## Verified release and schema

Main/origin/main a79771107185628bae251ab6746a4c3dc7d76f1c, PR76 merged.
Render dep-dbbbm7mk1f9s73bmaqk0 live 20 October 06:22:28 IST.
PR76 branch adf06cd6a7ab12e831f2c09b7671ecb0f0e184d7: 1,290 unit,
125 integration, 15 browser checks passed. Tests run39349940889, Verification
39349940946, E2E39349940880. Independent adversarial QA and bounded PM acceptance.

Ledger schema20261019145430 is applied. Owner explicitly approved the scoped
runtime access proposal on20October; migration20261019152513 is applied.
Existing worker role has SELECT/INSERT/UPDATE plus role-specific RLS policies.
No DELETE/TRUNCATE/browser access, new credential, role membership or bypass.
All three tables retain RLS; anon/authenticated denied; security advisors no lints.
Retention index20261020004623 is applied. No production retention deletion run.

## Controlled live verification

Run39277563309 first attempt failed BEFORE acquisition: worker role lacked access.
After approved migration, failed job was rerun through GitHub connector, attempt2,
job118392295466. Attempt2 SUCCEEDED. Supabase independently confirms exact batch
53377108-7ad5-5e82-8584-7f0aad9d9944: 30 accepted observations, 30 memberships,
30 positives, both completeness/absence flags false. Completed20October
06:22:34 IST. This is one controlled batch, not sustained operation.
Original source/make inputs: existing queued CarTrade / Hyundai, one job/page budget.
Do not count negative-only, empty, deferred or superseded work as positive proof.
Global CARSCANNER_SCAN_LEDGER_ENABLED remains off/default; only controlled process
opts in. Successful membership proves accepted writes, not physical availability,
source completeness or national breadth.

## Retention and next P1-02 work

src/scan_ledger_retention.py defaults dry-run: minimum30days; max10generations,
100batches,1000members; candidate50/hard200. Locks queue then generation, then
batches before membership counts. Protects active work, current/malformed
continuations, recent/incomplete/oversized history. Whole-generation deletes affect
audit children only; canonical vehicles/listings/observations and queues untouched.
Caller owns commit; timeout settings restored on success and rollback on failure.
No schedule invokes cleanup. Operational dry-run/retention evidence is still open.

Next highest-priority dependency: sanitized bounded parser evidence + offline
replay for one named reviewed strategy. Explicit unsupported/truncated/unavailable
states, version/hash/source/generation linkage; no raw bootstrap/session secrets,
buyer payload or historical re-ingestion as live. Review LLD before editing.
P1-02 remains incomplete. Then P1-03 enumeration and measured P1-04 source expansion.

## Continuation

Local Python ../test-env/Scripts/python.exe -X utf8; TEMP/TMP ../test-temp.
Local PostgreSQL sockets remain blocked; skipped tests are not passes. CI supplies
real disposable PostgreSQL. Existing ignored .env secrets must never be printed.
Reuse continue-carscanner-phase-1 heartbeat; no duplicate reminder or exact reset
restart claim. Free testing, alerts dry-run; no paid activation/customer messages.
Save exact branch/files/CI/deploy/blocker before stopping; preserve user edits.
