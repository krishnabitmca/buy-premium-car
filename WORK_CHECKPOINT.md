# CarScanner continuation checkpoint

Updated 19 October 2026, evening IST. Read AGENTS.md, CARSCANNER_PROFILE.md,
CURRENT_STATE.md and required product/architecture/decision documents first.

## Actual repository and application state

Main and origin/main synchronized to c51e6174aca2139671238200af370931dc485d66.
PR 72 saved the team/product/state memory. PR 73 delivered the optional private
accepted-observation collector prerequisite for P1-02. No worker uses it yet;
no durable membership tables, parser replay capture or absence authority exists.

Render dep-dbb2ih1srm7s73b1kmdg became live 19 October 20:00:15 IST on c51e617.
Production smoke run 39269400141 and deployed QA run 39269400218 passed.
QA: 61/61, no browser errors, job 118117421792. Main Tests and Verification passed.
Exact PR branch CI: 1,242 unit, 78 integration and 15 browser tests passed.
Independent backend/QA reviews approved; PM accepted this prerequisite scope only.
PM requested consolidating this checkpoint; obsolete stage claims are now removed.

Local focused tests: 13 passed; independent ingestion unit checks: five passed.
Local PostgreSQL tests were blocked by WinError 10013 and are not counted passing.
Dedicated initdb completed; pg_ctl cleanup found no live server process. Preserve
../postgres-membership-test for inspection, rather than deleting it.

Only this checkpoint and CURRENT_STATE.md may have intentional uncommitted agent
operational updates after the merge. Inspect actual git status; preserve user edits.
No schema, credentials, paid services or customer notifications changed.

## Exact next task — P1-02 durable ledger

1. Create a focused feature branch from current main, preserving operational notes.
2. Read docs/SCAN_MEMBERSHIP.md, src/scan_contract.py, inventory_ingestion.py,
   inventory_lifecycle.py and inventory_refresh_worker.py. The reviewed LLD and
   adversarial matrix are in ../../outputs/P1_02_SCAN_LEDGER_LLD_2026-10-19.md.
3. Use the verified cached Supabase CLI 2.81.3:
   ../npm-cache/_npx/5472f65ac9020734/node_modules/supabase/bin/supabase.exe
   Its --version and migration new --help passed. Generate the additive migration
   with this CLI; never invent filenames. The newer cached CLI fails creating
   a user-profile config directory; no HOME override or permission expansion needed.
4. Implement private source-consistent generation, stable claim/batch and accepted
   observation membership records, using actual IDs from the new collector.
   Wire inside the existing post-HTTP claimed transaction with canonical writes
   and checkpoint. Keep provisional IDs transaction-local and discard on rollback.
5. Test atomic rollback, late/superseded claims, commit replay, overlapping scopes,
   config/version restart, legacy partial history, repeated observations and source
   mismatch. Exhausted/partial/failed scans never authorize omission-as-sold.
6. Add bounded retained sanitized parser evidence/offline replay for one reviewed
   strategy, explicit unsupported/truncated states and safe retention. No raw
   session/bootstrap/credential capture and no historical re-ingestion as live.
7. Run real disposable PostgreSQL checks (CI works), security review/advisors and
   independent backend/QA review. Deploy schema before enabling worker use, verify
   actual operation separately, then update this checkpoint and application state.

P1-02 remains incomplete. Do not repeat the collector implementation or claim it
is the ledger. P1-03 enumeration and P1-04 measured source expansion remain next.

## Runtime and continuation references

Local Python: ../test-env/Scripts/python.exe -X utf8; TEMP/TMP: ../test-temp.
Local preview/DB health must be checked; open tabs do not prove working services.
Linux CI runs disposable PostgreSQL/Redis and browser checks. Existing ignored
.env contains approved secrets; never print or commit it. GitHub connector works.

Active same-chat hourly continuation: continue-carscanner-phase-1. Reuse it; do
not create duplicates. Scheduled retries require available execution, computer on,
app running and repository access; no exact quota-reset restart guarantee.
Keep infrastructure free and alerts dry-run. Save exact branch/files/test/CI/deploy
state after meaningful work and before stopping when possible. Respect owner
pause/cancel; do not overlap writers or bypass approval/usage limits. Stay quiet
on unchanged non-actionable state and report meaningful changes or needed input.

## In-flight next increment — durable ledger

Branch feat/durable-scan-ledger adds private generation/batch/observation membership
schema (CLI-generated 20261019145430_inventory_scan_ledger.sql), validated helper
and gated worker integration. CARSCANNER_SCAN_LEDGER_ENABLED remains false by
 default; no production migration or activation has occurred. Independent backend
review approved schema/worker boundaries. QA added 18 database cases, including
worker rollback/retry, two-batch continuation and actual browser-role denial.
Local focused checks: 31 passed; dedicated ledger suite: 18 unit passed and
18 DB skipped (not accepted as DB passes). CI PostgreSQL verification is next.
Existing production security-advisor baseline returned no lints; this does not
validate the new unapplied schema. See ADR 029 and docs/SCAN_LEDGER.md. Replay,
retention and controlled production activation remain open. Do not confuse the
new feature branch with live runtime c51e617 or reimplement prior collector code.
