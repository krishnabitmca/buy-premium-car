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
