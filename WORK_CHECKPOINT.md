# CarScanner continuation checkpoint

Updated 19 October 2026, Asia/Kolkata. Read AGENTS.md and CARSCANNER_PROFILE.md first.

## Current task

Save owner-requested team/product/state memory and configure same-chat recurring
continuation. Documentation branch: docs/carscanner-team-memory, based on verified
application main 5921c87f616eeb705dde9b0b01a5d397856aa6ae. These memory documents
are not themselves a new application release. Check git status/current branch
and remote PR state rather than assuming a clean main checkout.

Active same-chat continuation: continue-carscanner-phase-1, hourly. It was created
successfully in the app on 19 October 2026. Reuse/update it instead of duplicating.
It retries at its schedule when execution is available, not an exact quota-reset
event. Local work requires the computer on, the app running and repository access.

## Resume engineering at P1-02

1. Inspect current branch/diff, latest main, docs/PHASE1_EXECUTION.md, ADR 028,
   src/scan_contract.py, src/source_adapters.py and src/inventory_refresh_worker.py.
2. Define the small schema/LLD for durable scan generations and listing membership,
   bounded retained parser evidence and versioned replay. Reuse fenced canonical
   ingestion/checkpoint transactions; do not hold transactions during network I/O.
3. Test crash/retry/late claims/config changes and overlapping scopes. No partial,
   failed or exhausted-unverified scan may remove stock or imply sold/completeness.
4. Obtain independent backend/QA review, focused PR and actual runtime verification.
   Keep PostgreSQL serving safety; do not add paid services or enable blanket absence.
5. Update CURRENT_STATE.md and this checkpoint with exact changes, evidence and
   unresolved work before moving to P1-03/P1-04.

P1-02 has not been implemented yet. Do not claim saved metadata is durable membership.
Use relevant Supabase/Postgres skills before schema work; CLI-generated migration
names and review/security checks are required by applicable skill instructions.

## Local execution references

Repo: work/buy-premium-car under this chat workspace. Local Python test runtime:
../test-env/Scripts/python.exe -X utf8. Set TEMP and TMP to ../test-temp.
No local Playwright installed in this runtime; Linux CI runs browser and disposable
PostgreSQL integration checks. Existing ignored .env may hold approved credentials;
never print, copy into memory, or commit it. Local DB/preview health needs rechecking.
GitHub connector is available for publishing; do not assume shell network permission.

## Stop/resume rules

Save checkpoint while tools still work, including branch/commit, changed files,
tests passed/failed/not run, pending CI/deploy IDs, next action and exact blocker.
Do not make duplicate continuation automations. If usage is unavailable, retry on
the existing schedule; do not bypass limits, spend credits or activate paid plans.
If the owner pauses/cancels, stop continuation and reflect it here. No overlapping
writers, unsafe publishing or incomplete work reported as done. Keep unchanged
non-actionable states quiet. External access/labels/devices may need owner input.
