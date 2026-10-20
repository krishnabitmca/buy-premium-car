# CarScanner current state — dated evidence

## Local replay increment — 20 October 2026

Owner research/profile committed7c75abf; operator-only sanitized Fusion capture
and offline replay committed386700c on feat/sanitized-parser-replay. 84 focused
tests passed; historical samples cannot ingest, refresh or retire inventory.
Independent review, final full regression and PR/CI are pending. P1-02 remains
open. GitHub main is now6d93c9f after owner-merged PR79 source-concentration
measurement; feature branch incorporates it. Its production deployment was not
verified in this increment. Older release evidence below remains dated evidence.

Final local regression now passed: 1389 tests, 3 skipped, 125 integration
deselected; 84 focused and 20 HTTP tests passed separately. Independent review
and GitHub CI remain pending; no production change is claimed.

## Owner research memory update — 20 October 2026

All four owner research sources read: two complete PDFs (24/30 pages) and two
concept boards. Requirements synthesized in
docs/OWNER_UX_BACKEND_RESEARCH_2026-10-20.md and linked from CARSCANNER_PROFILE.md
and startup instructions. Source assets/hash manifest archived locally under
../../outputs/owner-research-2026-10-20/; not published to GitHub. Research ingestion
changes documentation only, not runtime behavior or production evidence. Evidence
cards → comparison matrix → optional guidance is the recorded direction; immediate
P1-02 acquisition/replay dependencies remain. No new tests/deployments in this slice.

Saved 20 October 2026, Asia/Kolkata. Revalidate on resume; do not assume this
snapshot establishes current health, current inventory or a freshness SLA.

## Last verified application release

- Repository: https://github.com/krishnabitmca/buy-premium-car
- Hosted application: https://buy-premium-car1.onrender.com/
- Last verified live application commit: 0acd915ca1f50beeff2d771590e362673f2690de.
- Latest code PR 81: https://github.com/krishnabitmca/buy-premium-car/pull/81
- Render deploy: dep-dbbjkbmk1f9s73btvip0; live 20 October 15:24:22 IST.
- Local preview URL: http://127.0.0.1:8000/; not reverified in this memory-saving
  task. An open browser tab is not evidence that the local server is healthy.

Python APIs/Gunicorn/WSGI, responsive index.html and PWA shell; PostgreSQL canonical
vehicles/listings/observations and durable acquisition/renewal queues. Registry
governance, source-specific adapters, claim fencing, origin leases, latest-observation
and expiry rules exist. Ordinary summary search currently serves PostgreSQL;
Elasticsearch is a guarded trial projection and does not provide ordinary HTTP
serving parity or incremental indexing. Gemini is an optional consented free-tier
pilot, constrained intent/evidence selection, with a durable 30-call/day cap.
Device-local saved choices/compare/share do not establish verified user accounts.

PR 71 added scan generation/configuration fingerprints and truthful unverified
coverage. Frontier exhaustion never authorizes absence retirement. It did not
add sources or inventory, durable scan membership or authoritative completeness.

## Recorded validation and supply evidence

- PR 73 exact branch: 1,242 unit, 78 integration, 15 browser tests passed.
- Deployed QA: 61/61, no browser errors; run 39269400218, job 118117421792.
- Production smoke: passed, run 39269400141. These are dated functional checks,
  not national recall, long-running freshness or load measurements.
- Manual deployed Honda City Used-only: 47 observations/three sources with partial
  coverage disclosure and original seller links; some photos unavailable.
- Earlier 19 October eligible snapshot: 6,598 used + 119 demo + 38 unknown-condition
  offers, 12 sources, 45 raw brand labels. These are source offers, not unique
  physical cars, normalized taxonomy completeness or national market recall.
- Three marketplaces dominate supply. Observed scheduled dispatch gaps were about
  two hours despite quarter-hour configuration. Always-on capacity is unproven.

Detailed evidence: docs/PHASE1_EXECUTION.md; sibling workspace report
../../outputs/TEAM_PHASE1_REVIEW_2026-10-19.md.

## Open gates and next dependency

PR 74 delivered private transactional generation/batch/observation membership.
PR 75 added exact-claim controlled verification. Its first live attempt failed
before acquisition because the existing runtime role lacked ledger access.
Owner approved the narrow SELECT/INSERT/UPDATE plus role-specific RLS migration;
it is applied, with no browser/delete privilege or new credentials. Security
advisors now return no findings. Controlled run39277563309 attempt2 succeeded; Supabase independently confirms
batch53377108-7ad5-5e82-8584-7f0aad9d9944:30 accepted observations,30 positive
memberships, false completeness/absence flags. Global gate is off. This proves
one controlled write batch, not sustained acquisition or current availability.

PR 76 adds bounded whole-generation ledger retention, default dry-run, unscheduled.
Canonical inventory is preserved. Candidate index applied. Code passed 1,290 unit,
125 integration, 15 browser tests; independent QA found/fixed membership growth
race and PM accepted this bounded scope. Production cleanup has not run. Bounded
parser evidence/replay and operational retention acceptance remain open.

P1-01 initial evidence contract delivered; complete feature remains broader.
Next P1-02: durable scan generations/membership and bounded parser replay evidence.
Then P1-03 reviewed source-specific enumeration. P1-04 source breadth/demo feeds
may proceed alongside projection design, selected by measured missing supply.

Other open gates: candidate false merges/provenance/audited split; unknown-condition
UI fallback; incremental outbox/indexing and ordinary HTTP Elastic parity; stable
pagination; measured freshness/backlog/load/restore; image/link quality; verified
watch ownership/session expiry/revocation/abuse controls; real devices/accessibility
and buyer evaluation. Public watch email-only bootstrap/query-token behavior is a
security blocker. Alerts remain dry-run. Controlled testing only, not Phase 1
national production-ready. The eight broad product groups and A01–A15 overlap.

Rollback reference: application commit 57974754e6de28f2fed516660aa9e473d9588992,
Render dep-dbape5flk1mc73d45p70. No rollback drill executed; check artifact
availability, compatibility and auto-deploy settings before any rollback.

## Demo search incident, 20 October

Verified All brands/Demo search works but indexed eligible supply initially
contained only Mercedes across2sources (72sourceoffers, not uniquephysicalcars).
BMW Demo zero reproduced. PR80 fixes brandless jobs ignoring literal configured
demo routes, resets old-root generations and preserves perlisting condition rules.
Guarded Tata feed rollout now yields one buyer-visible Altroz demo at8.51lakh,
explicit on-road basis, originaldealerlink, unknownmileage/no vehiclephoto.
Controlled run39396781228 and independent canonical DB read confirmed ingestion.
BMW configured OEMdemo page currently empty; broader demo coverage remains an
active gap. No all-brand coverage claim, freshness relaxation or inferred demos.
PR80 branch1,317unit/125integration/15browser passed; main smoke39396671396 passed.

## Worker-environment source evidence

PR81 adds manual bounded public diagnostics, no ingestion or DBcredentials.
Sundaram probe39404096044 returned HTTP403, no retry, no parsed/ingested rows.
It remains outside live registry. This is a verified acquisition blocker, not
zero market inventory. BranchCI1,331unit/125integration/15browser passed.
Parser replay and wider accessible demo feeds remain open priorities.
