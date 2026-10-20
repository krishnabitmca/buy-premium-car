# CarScanner current state — dated evidence

Saved 19 October 2026, Asia/Kolkata. Revalidate on resume; do not assume this
snapshot establishes current health, current inventory or a freshness SLA.

## Last verified application release

- Repository: https://github.com/krishnabitmca/buy-premium-car
- Hosted application: https://buy-premium-car1.onrender.com/
- Last verified live application commit: 25c4a5c37afe02eba721be1d5541acd925b55a25.
- Latest code PR 75: https://github.com/krishnabitmca/buy-premium-car/pull/75
- Render deploy: dep-dbb3bp5g1s2s73buh7mg; live 19 October 20:53:41 IST.
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

PR 74 delivered private transactional generation/batch/observation membership,
using the PR 73 accepted-ID collector. The additive migration is applied; all three
tables have RLS and no browser privileges. Global worker gate remains off. A
manual, one-job controlled verification (PR75) failed before acquisition because
the existing private runtime role lacks ledger access. Run39277563309. A narrow
server-role grant is prepared but NOT applied; owner approval is pending.
No live ledger batch is verified yet. Retention code is in progress on
feat/bounded-ledger-retention, dry-run default and not scheduled.

PR 74 branch CI: 1,260 unit, 96 integration, 15 browser tests passed; 61/61 QA.
Main Tests 39275425220, Verification 39275425177, E2E 39275425251 and production
smoke 39275425271 all passed. This does not establish live ledger operation.
Security advisors show three expected INFO no-policy notices for deny-all private
tables, no WARN/ERROR. Parser replay and bounded retention remain open.

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
