# CarScanner continuation checkpoint

## Resumed engineering increment — 20 October 2026

Final local full regression after merging main6d93c9f: 1389 passed, 3 skipped,
125 integration deselected, 39 existing utcnow deprecation warnings, 85.99s.
Focused84 and HTTP20 passed separately. No database/browser/deployed acceptance
claimed. Local checkpoint commit7e14219; ordinary git push failed because Git's
credential/prompt shell cannot create its MSYS named object under sandbox.
Use approved GitHub connector tree/commit/branch APIs for draft publication;
never print credentials or change authentication. Remote publication snapshot
may have a different commit ID from local history; reconcile trees before resume.

Owner asked to resume with latest research in mind. Research/profile is committed
as 7c75abf; operator replay as 386700c on feat/sanitized-parser-replay. Added
tests/test_parser_replay.py covering real fixture parity (3 positive/1 sold),
drift, corruption, metadata, five-card bounds, context reset and malformed input.
Fixed vacuous captures with zero normalized evidence and credential/contact URL
path guards. 84 focused replay/reviewed-parser/listing-evidence tests passed.

Initial broad run: 1362 passed, 3 skipped, 125 integration deselected, 20 localhost
HTTP failures caused by sandbox WinError10013. After session network grant, all
20 HTTP cases passed. Final full run after latest guards and main reconciliation
is pending at this checkpoint; never describe the initial broad run as green.

GitHub main independently changed: PR79 merged by owner, main6d93c9f, only
src/coverage_operations.py and tests/test_coverage_operations.py. Fetched and
merged origin/main into this feature branch without overlap. An attempted
ff-only merge after the profile commit correctly refused divergence; subsequent
normal merge succeeded. Production deploy for main6d93c9f not checked here.
Independent backend/QA agents remain usage-limited; no replacement spawned to
bypass limits, no independent replay acceptance claimed. Prepare draft PR/CI,
leave unmerged pending review. Automatic capture/storage/retention and P1-02
operational acceptance remain open; no acquisition or production changes.

## Latest owner request completed: research/profile ingestion — 20 October 2026

Read both PDFs in full (24 + 30 pages), reviewed rendered pages and both supplied
concept boards. Added docs/OWNER_UX_BACKEND_RESEARCH_2026-10-20.md with source
hashes, UXB-01–17 requirements, acceptance, backend contracts, visual guidance,
measurement, sequencing and explicit research-versus-implementation limits.
Updated CARSCANNER_PROFILE.md, AGENTS.md and CURRENT_STATE.md. Full assets/text/
renders/hash manifest preserved locally in ../../outputs/owner-research-2026-10-20/;
source files are not in Git/public uploads. Scope is repository project memory,
not account-wide/plugin-wide memory. Documentation-only; no runtime tests/deploy.

Current branch feat/sanitized-parser-replay, base 0acd915ca1f50beeff2d771590e362673f2690de.
Research edits remain local/uncommitted. Preserve pre-existing dirty operational
memory notes and unfinished parser replay files: DECISIONS/030-sanitized-offline-
parser-replay.md, docs/PARSER_REPLAY.md, scripts/parser_replay.py,
src/parser_replay.py, tests/test_parser_replay_cli.py and
tests/test_parser_replay_privacy.py. Independent backend/QA work was interrupted
by usage limits; no completed replay review/test gate can be claimed. Do not
include unfinished code in a research-only commit or bypass usage limits.

Next engineering action: reconcile partial replay module/CLI/privacy tests with
the existing sanitized Fusion replay design, finish missing unit coverage, run
focused meaningful tests, obtain available independent QA, then focused PR/CI.
Read the newly saved research before related UX/evidence work; it does not move
optional AI/UI ahead of P1-02. Existing Sundaram403 blocker remains unchanged;
do not repeat unchanged probe or activate it. Free testing/dry-run alerts remain.

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

## Latest documentation and next design anchor

PR77 merged as142ec976531bdad3292469c6e59c5ccfb51b8f49; local main/origin/main
synchronized. This checkpoint may contain intentional uncommitted operational
notes after that merge. PR77 branch checks all passed; verify its final deploy
and main runs before claiming that documentation release live.
PR76 production smoke39350134392 and main Tests/Verification/E2E passed.
Next reviewed design: ../../outputs/P1_02_FUSION_REPLAY_LLD_2026-10-20.md.
Independent backend recommends Fusion fusion_cards, existing parser/tombstone
functions, sanitized allowlisted sample and taxonomy ContextVar for offline replay.
No implementation started. Re-read actual code and privacy constraints first.

Final deploy verification: docs release142ec976531bdad3292469c6e59c5ccfb51b8f49
is live on Render dep-dbbbo5g473hc73ddmfi0,20October06:26:22IST.
Production smoke39350535857 passed. Main Tests39350535954,
Verification39350535829 and E2E39350535867 were still running at checkpoint;
branch checks for the same documentation content already passed. Check final
main outcomes on resume. Only CURRENT_STATE.md and this checkpoint intentionally dirty with final
operational evidence; no code edits.

## Owner demo-search incident takes priority over replay

Branch fix/global-demo-acquisition-routes based main142ec9. Preserve existing
memory edits. Actual production All brands/Demo returns results but all eligible
supply is Mercedes; BMW returns0. Rootcause: emptyquery bypasses configured BMW
condition route, queue continuation holds genericusedroot. Adapterfix plus real
resolver/checkpointtests, Gurudev feed numeric/type/collision guards implemented.
Focused60tests passed. Independent QA review pending; no runtime rollout yet.
Next publish PR/CI then merge/deploy; controlled BMW demo job must use newroute
and original perlistingdemo evidence. Gurudev source absent from registry despite
existingcode/YAML; publicAPI verifiedonepricedAltroz. Register only that reviewed
source afterQA/codeCI and runonebounded acquisition, verifyactualTataDemoUI.
Do not globally seed/override registry, infer usedasdemo or extend freshness to
hide supply failures. Sundaram previously403 requires verification, not activation
by configuration alone. Return to parserreplay after incident checkpoint.

## Demo incident delivery — 20 October 2026, 14:30 IST

PR80 merged and deployed as49126d0641b13db7139eccc733b704d4546b9bf2.
Local main/origin/main synchronized. Render dep-dbbio20473hc73dka7a0 live
14:24:05 IST. Main Tests39396671456, Verification39396671458, E2E39396671388
and production smoke39396671396 passed. Branch373a973:1,317unit,
125integration,15browser passed; independent QA approved. Broad live-catalogue
matrix39396433303 was still running separately; do not claim its completion.
Remote unrelated PR79 remains open; not merged or edited.

Registered ONLY previously configured Gurudev Tata Demo after current public API
review and parser guard tests. Newly created source/capabilities/verified adapter/
endpoint/global-demo job in one transaction, preserving all existing registry
state. Rollout SQL ../../outputs/gurudev-demo-reviewed-rollout.sql.
Controlled acquisition39396781228/job118541365426 succeeded on the deployed code.
Canonical latest row: Tata Altroz, demo,8.51lakh,on_road,live_verified,true;
observed20October14:24:40IST, sold_signal false. Production browser
Demo only/Tata returned1result with originaldealerlink and unknownmileage/photo.
Proof ../../outputs/tata-demo-production-result.png. No inferred stock or expiry
relaxation. Global ledger gate stays off outside bounded verification.

BMW dedicated configured demo URL currently visibly returns No listings found;
fixed brandless route selection cannot manufacture BMW supply. Sundaram source
still not activated: prior worker403, publicpage has explicitdemo cards but needs
actual bounded-worker validation. Wider all-brand demo acquisition remains OPEN.
Next incident priority: source-specific current demo supply across missing brands,
reviewed dealer/OEM/feed rollout and sampled buyer-visible checks. Add maintained
empty/coverage diagnostics before calling this all-brand working. Keep parser
replay LLD queued as following P1-02 work; owner demo incident takes priority.
Only CURRENT_STATE.md/WORK_CHECKPOINT.md intentional operational dirty files.

## In-flight source probe, 20 October heartbeat

Current branch feat/bounded-demo-source-probe based49126d; remote main checked
unchanged, unrelatedPR79 still open. Backend agent owns scripts/probe_demo_source.py
and tests/test_probe_demo_source.py. Root owns manual workflow/demo-source-probe.yml
and docs. QA read-only review. No overlapping writers or source activation.
Probe is public-only, two reviewed YAML source choices, single bounded request,
no redirects/retries, DB credentials or ingestion. Never bypass403. Output sanitized
counts + max5publicoffer summaries, no rawHTML/session/bootstrap/contact payloads.
After tests/review publish focusedPR and realGitHubprobe Sundaram beforeactivation.
If403/oversized/parserfailure, preserve unavailable status; do not seed it live.
Broad livecatalogmatrix39396433303 ended cancelled, not passed. Existingdemo
incident rootfix andTata liveproof remain lastcompleted increment. Parserreplay
stillopen afterfocused source investigation. Preserve operationaldirtymemoryfiles.

Probe PR81 published: branch33b8bcafc1903af90cd141afad50cd8af0d6bc0c.
31 focused tests passed; independent QA approved. CI Tests39403803965,
Verification39403804292, E2E39403804099 in progress at publication.
Next wait relevantchecks, merge/deploy, manually run Reviewed Demo Source Probe
for Sundaram from main. This workflow has noDBcredentials and doesNOT activate
or ingest it; inspect JSON status rather than treating greenjob as availability.
Only checkpoint may have postcommit operational edits. Actual source activation
and persistent parser replay still require separate reviewed evidence.

## Source probe completed — 20 October 2026, 15:25 IST

PR81 merged as0acd915ca1f50beeff2d771590e362673f2690de; localmain/origin/main
synchronized. Render dep-dbbjkbmk1f9s73btvip0 live15:24:22IST.
Branch33b8bcaf:1,331unit,125integration,15browser passed; independentQAapproved.
Actual publicprobe39404096044/job118565691126 returned HTTP403 from Sundaram
at15:24:40IST. Greenworkflow means diagnostic completed, NOT available stock.
Exactlyoneattempt, no redirects/retries, parsed0, ingestedfalse, authorityfalse.
Report ../../outputs/sundaram-worker-probe-2026-10-20.json. Sundaram NOT registered
or activated. Do not retry unchanged403 everyheartbeat, bypassit or loadfixtures.

Next unblocked P1-02 dependency: sanitized Fusion sample + offlineexistingparser
replay per ../../outputs/P1_02_FUSION_REPLAY_LLD_2026-10-20.md. Broaderdemo sources
stillneedreviewedaccessiblefeeds. IfSundaramaccesschanges later, first replace
production fetch_sundaram10page/threadpool branch with budgeted existingfrontier;
onlyadvertisedsameorigin/listings/page/N URLs, no synthesizedintermediatepages,
correctpending/resume/failurestates. Backendread-onlydesign delivered, no codeyet.
Main CI/deploy results afterPR81 stillneed finalrecheck beforeclaimingallsuites.
Onlystate/checkpointoperationalnotes maybedirty. No source/security/spend changes.

Final PR81 main checks all passed: Tests39404020291, Verification39404020056,
E2E39404020060, production smoke39404020022. Diagnostic JSON HTTP403 also
visibly confirmed in GitHub UI; screenshot ../../outputs/sundaram-worker-probe-blocked.png.
No new stock/source activation in this increment. Resume sanitized Fusion replay
without repeating unchanged Sundaram403. Main/origin/main0acd915; only two memory
files intentionally dirty with final operational evidence. Existing automation
remains active; Phase1 acceptance not reached.


## Controlled parser capture implementation — 20 October 2026

Branch `feat/bounded-parser-capture` is based on `origin/main`
`9ff570bee029a8c980588d4c45f48c13e13c74c0` (merged PR82). This increment
adds an explicitly gated, Fusion-only in-memory capture hook to the existing
one-job controlled ledger verifier. It reuses the fetched response, accepts at
most two sanitized samples, validates replay and source/generation identity,
and exports fixed files plus a receipt only after the exact committed claim is
read back. Raw HTML is never written. Capture/export failure does not retry or
mark committed inventory failed. No database/schema/role/credential/source or
continuous-collection change is included.

Changed files: `.github/workflows/scan-ledger-verification.yml`,
`src/parser_capture.py`, `src/source_adapters.py`,
`src/inventory_refresh_worker.py`, `scripts/verify_scan_ledger.py`,
`tests/test_parser_capture.py`, `tests/test_parser_capture_wiring.py`,
`DECISIONS/031-controlled-parser-capture.md`,
`docs/CONTROLLED_PARSER_CAPTURE.md`, `CHANGELOG.md`.

Validation: focused 47 passed, 1 Windows symlink-privilege skip. Full local
regression 1,433 passed, 129 skipped, 39 pre-existing utcnow warnings in
123.51s; compileall and diff-check passed. Local skips are not CI/database/
browser passes. Independent QA agent attempted review but hit its own usage
limit; do not claim independent acceptance.

Next: publish focused draft PR, inspect GitHub CI including disposable Postgres
and browser checks, merge only if green, verify Render deployment, then dispatch
exactly one existing eligible Fusion queued job with `capture_sample=true`.
Inspect the seven-day artifact receipt/hash/replay without exposing sample
content. If no eligible queued job exists, report the operational blocker; do
not synthesize inventory or broaden access. Global ledger/capture gates remain
off and P1-02 remains open until this controlled operational proof is complete.


## P1-03 discovery evidence increment — 20 October 2026

PR83 merged as b3c2c75414d969edd02891b86fe337ad155d1056. Render auto
webhook did not start, so after repeated absence the already-authorized deploy was
triggered once through Render. Deployment dep-dbbo86k9v7es73fsj6f0 is live for
b3c2c75; production homepage loaded successfully after refresh.

Controlled Fusion capture remains naturally blocked. Read-only Supabase evidence
shows one Fusion global/both job completed with last_success_at
2026-10-20T14:36:48.492514Z, only 33 minutes old when checked, versus a 360-minute
freshness target. Do not synthesize/requeue it early. Let the normal scheduler
create eligible work, then run one capture and validate hashes/replay.

Current eligible snapshot exposes demos only for Mercedes-Benz (72 offers/62
vehicles) and Tata (1/1). Candidate review: Gurudev Skoda publicly shows five
explicitly SOLD cars and no public asking prices; Porsche Finder is new/used,
not demo; GetOnRoadPrice timed out; DiscountedCarsIndia was inaccessible;
Motodeals exposed no parseable inventory. No source activated.

Branch feat/demo-discovery-evidence starts from local b58089c, whose tree is the
merged PR83 tree. Fixed discovery classification so query intent never becomes
page condition evidence. Returned title/snippet/normalized URL path alone may
classify demo/used; ambiguous dealer directories remain both. Added ADR032,
changelog and tests/test_discovery_evidence.py. Validation: 23 focused passed;
broader discovery/registry/control-plane/probe/adapter set 76 passed. Next:
publish focused PR, run CI, merge/deploy, then measure subsequent discovery output
and continue source-specific accessible feed acquisition. P1-03 remains open.
