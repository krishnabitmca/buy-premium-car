# CarScanner continuation checkpoint

Updated 19 October 2026, evening IST. Read AGENTS.md, CARSCANNER_PROFILE.md,
CURRENT_STATE.md and required product/architecture/decision documents first.

## Verified release and schema

Main/origin/main: 2a85af02b376ce6aaec107fbec80feb328d1cef7, PR 74.
Private ledger migration 20261019145430_inventory_scan_ledger.sql applied to the
approved Supabase project. First attempt aborted on lock timeout; inspection and
retry succeeded without weakening safeguards. Three tables have RLS, no browser
privileges; three expected INFO no-policy advisor findings, no WARN/ERROR.
Render dep-dbb358flk1mc73dfikd0 live 19 October 20:40:01 IST.
Main Tests 39275425220, Verification 39275425177, E2E 39275425251 and production
smoke 39275425271 passed. PR branch: 1,260 unit, 96 integration, 15 browser,
61/61 QA. Local PostgreSQL remains socket-blocked; skips are not DB passes.

Global CARSCANNER_SCAN_LEDGER_ENABLED stays false/default. No actual live ledger
batch verified yet. No new sources, credentials, costs or notifications enabled.

## In-flight increment: controlled ledger verification

Branch feat/controlled-ledger-verification based on verified main. New manual-only
workflow and scripts/verify_scan_ledger.py claim exactly one existing verified
source job with page budget one. Verification requires the exact refresh/attempt/
claim-time batch, positive membership, matching count and false authority flags.
Independent architect review approved after correcting time-window attribution
and negative-only acceptance. QA owns tests/test_scan_ledger_postgres.py and new
unit tests/test_verify_scan_ledger.py; inspect actual status before editing.

Next: finish local checks/review, publish focused PR, wait disposable PostgreSQL
CI including controlled verifier test, merge only green. Then invoke manual main
workflow through authenticated GitHub UI (connector has no dispatch capability),
using an existing queued verified source/make. Confirm actual role and private
rows via Supabase. Do not enable sustained collection. If UI requires sign-in,
checkpoint exact dependency without claiming runtime proof.

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
