# CarScanner continuation checkpoint

Updated 19 October 2026, evening IST. Read AGENTS.md, CARSCANNER_PROFILE.md,
CURRENT_STATE.md and required product/architecture/decision documents first.

## Verified release and live blocker

Main/origin/main: 25c4a5c37afe02eba721be1d5541acd925b55a25, PR75 merged.
Render dep-dbb3bp5g1s2s73buh7mg live 19 October 20:53:41 IST.
PR75 CI: 1,269 unit, 97 integration, 15 browser, independent QA/architect reviewed.
Main Tests39277478087, Verification39277478197, E2E39277478120 passed.
Controlled live workflow39277563309/job118145782164 failed BEFORE acquisition:
existing carscanner_free_test_runtime lacks ledger access. It has no BYPASSRLS.
No actual ledger batch verified. Global gate remains off. Do not rerun until
narrow role access is owner-approved/applied and reverified.

Private ledger schema migration20261019145430 is applied; RLS/browser denial
verified. Proposed20261019152513 runtimeaccess migration is NOT remotely applied.
It grants existingrole SELECT/INSERT/UPDATE plus command-specific policies only;
noDELETE/TRUNCATE/browseraccess/credentials. Ownerapproval has NOT been received.
No production retention deletion is authorized or performed.

## In-flight bounded retention

Currentbranch feat/bounded-ledger-retention based25c4a5c. New helper
src/scan_ledger_retention.py defaults dry-run, minimum30days, whole generations,
max10generations/100batches/1000members,50candidatewindow/hard200. Queue then
generation locks, batch locks before counting memberships; protects activejobs,
references/malformedcontinuations/recent/incomplete/oversized batches. Canonical
inventory untouched. Caller transaction owns commit; timeouts restored on success.
New unitfile21passed; retentionDB and runtimeaccessDB tests requireCI (26skips,
notpasses). QA corrected age fixtures and reviews concurrency/RLS. New CLI-generated
retention index migration20261020004623 also unapplied. CI integration filelist
updated. Narrowruntimeaccess proposal is prepared alongside operational code;
remote application requires ownerapproval separately from merging code.

Next: finish independent QA, run focusedchecks, publish focusedPR, require real
PostgreSQL CI and review beforemerge. Request ownerapproval of concrete tested
runtimeaccess proposal; do not expandaccess automatically. Then controlledworkflow
rerun ifapproved, verify exactbatch/role/membership with Supabase, globalgateoff.
Retention apply remains off and unscheduled. Afterretention acceptance continue
bounded sanitized parser evidence/offline replay. P1-02 incomplete.

## Following P1-02 dependencies

Implement inactive-generation bounded retention with active-continuation safety,
then sanitized bounded parser evidence and offline replay for one reviewed
strategy. Preserve explicit unsupported/truncated states. No session/bootstrap
secrets or historical re-ingestion as live. Real DB rollback/concurrency/security
checks and independent adversarial QA required. P1-02 remains incomplete.
Then P1-03 enumeration and P1-04 measured dealer/OEM/demo expansion.

## Runtime and authority

Local Python ../test-env/Scripts/python.exe -X utf8; TEMP/TMP ../test-temp.
Existing ignored .env holds approved credentials; never print or commit it.
Reuse continue-carscanner-phase-1 same-chat automation. Free testing only,
alerts dry-run, no paid activation/security expansion/customer messages.
Save exact files/commit/tests/CI/deploy/blocker after meaningful increments.
No exact usage-reset restart guarantee; respect owner pause/cancellation.
