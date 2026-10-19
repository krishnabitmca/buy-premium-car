# Phase 1 assessment and execution contract

Baseline: 57974754e6de28f2fed516660aa9e473d9588992, 19 October 2026.
Owner mandate: India-wide, all-brand used/demo search with continuous acquisition.
Verdict: **controlled testing; Phase 1 release gates remain open**.

## Team responsibilities

These are AI review roles, not a claim of a staffed human team or years served.
Separate backend, product and QA agents independently inspected the baseline.
The coordinator reconciles findings, implements focused changes and requests a
separate diff review. The requested ten SDE and five QA personas define workstreams,
not ten/five simultaneously staffed people or completed reviews.

Outbound PM owns missing-supply evidence/customer advantage; inbound PM owns
requirements and acceptance. Backend/UX architects own consistency and interaction
designs. Engineering owns acquisition, parsing, lifecycle, identity, projection,
API, web, mobile/accessibility, operations and security. QA separately challenges
customer contracts, source truth, lifecycle/resilience, performance and devices.
Architect review and PM acceptance follow evidence. Screenshot-based UX review,
real-device acceptance and customer research remain pending, not completed here.

## Current-state assessment

| Layer | Retain | Evidence-backed gap |
|---|---|---|
| Web/mobile | Simple responsive search, seller links, saved choices, public PWA | index.html conditionOf defaults unknown to Used/source-inferred Demo; actual Android/iOS and assistive-technology acceptance missing |
| API | Typed constraints, whole-result filters, India-wide destination context | api/search.py source-name presence was treated as coverage completeness; corrected in first increment |
| Canonical data | PostgreSQL vehicles/listings/observations, latest-evidence expiry | No complete-scan membership; candidate attribute buckets can group distinct physical cars; provenance/revisions and audited merge/split incomplete |
| Acquisition | Reviewed adapters, continuation, fenced queue writes, origin leases | No authoritative complete enumeration or retained-document replay; lease is coarse and not renewed |
| Registry/discovery | Durable governance, staged candidate review, advertised scopes | Wider city/dealer/OEM/demo acquisition and feed access; registered sources are not observed stock or recall |
| Retrieval | PostgreSQL serving, guarded Elasticsearch trial | with_summary bypasses Elastic for ordinary requests; global revision invalidates whole index; standalone worker has no publisher |
| Operations | Gunicorn, bounded admission/readiness, scheduled jobs/artifacts | Roughly two-hour observed dispatch gaps despite quarter-hour configuration; sustained freshness, capacity, restore and recovery unproven |
| Security | Private server credentials, registry RLS, AI consent/quota | api/watch.py email-only token bootstrap, query tokens and no expiry block public watch readiness; keep alerts dry-run |
| Tests/CI | Unit, disposable DB, browser and production smoke | Passing suites do not establish recall, physical identity, national load or nonempty demo acquisition |

The delivery report recorded 1,234 unit, 72 integration, 15 Chromium and 61 deployed
QA checks for the baseline. These are historical results, not reruns of this change.
The last snapshot contained 6,755 eligible source offers across 12 sources,
dominated by three marketplaces. Offers are not unique cars or national recall.
The seven-card benchmark demonstrates instrumentation, not market acceptance.

## Practical target architecture

```mermaid
flowchart LR
 D[Reviewed discovery: links, sitemaps, feeds] --> R[Source registry and policies]
 R --> Q[Durable acquisition and renewal queues]
 Q --> W[Origin-budgeted background workers]
 W --> E[Retained evidence and versioned parsing]
 E --> N[Normalization and identity conflict handling]
 N --> P[Canonical PostgreSQL and scan membership]
 P --> O[Transactional projection outbox]
 O --> I[Idempotent index publisher]
 I --> S[Serving projection: expiry, filters, counts, ranking]
 S --> A[Public search API]
 A --> U[Responsive web and mobile shell]
```

Retained fetch evidence, membership, outbox and independent serving projection are
target components, not delivered by this diagram. Keep PostgreSQL canonical and
its queues initially. Independent processes may share this repository. Do not add
Kafka/Kubernetes/sharding/blind result caching without measured need. PostgreSQL
remains the truthful ordinary serving backend until projection parity is proven.
Never remove global index fences before entity-version/tombstone safety replaces
them. Observe queue age, freshness, lag, failures and cost at each boundary.

Lifecycle: discovered → parsed → validated observation → eligible until policy
expiry. Explicit negative evidence retires its matching source offer. Fetch
failure/partial scans are inconclusive. No omission implies sold. Future complete
scopes may schedule missing-offer rechecks/quarantine; newer positive evidence
must fence older reconciliation. Other source offers remain independent.

## Prioritized requirements and acceptance

| ID | Deliverable / dependency | Closure gate | Status |
|---|---|---|---|
| P1-01 | Scan truth and truthful API coverage; no dependency | Generation retained across batches; changed scope/parser restarts; exhaustion never authorizes absence; one offer/source never complete coverage | Initial increment implemented, verification underway |
| P1-02 | Durable generation membership and parser replay; 01 | Ingestion/checkpoint/membership atomic under crashes/retries; saved samples detect yield/schema regressions; no cross-scope leakage | Open |
| P1-03 | Reviewed enumeration for first suitable source; 02 | Missing pages/count mismatches/empty vs challenge tested; scoped absence only rechecks, never blanket sold | Open |
| P1-04 | Measured source breadth including demo feeds; 01,02 before absence | Independent samples by source class/make/model/region/condition; parser/API contracts and actual seller handoff per rollout | Open |
| P1-05 | Condition, attributes and identity truth; 01 | Unknown never silently Used/Demo; candidate vs confirmed distinct; labelled false-merge evaluation; audited reversible decisions | Open |
| P1-06 | Incremental projection; canonical consistency contract | Transactional outbox, idempotent/out-of-order consumers, replay, urgent negatives/source disables, expiry and observed lag | Open |
| P1-07 | Ordinary HTTP serving parity and stable pagination; 06 for independent Elastic | Actual backend asserted; full filters/counts/cohorts/order; cursor/snapshot under updates; bounded fallback | Open |
| P1-08 | Sustained workers and operational recovery; 02,06 | Multi-day freshness/queue-age/throughput evidence, source outages, process loss/restart, restore drill | Open; free schedule is no SLA |
| P1-09 | Public security boundary; before public watches | Verified ownership, expiring/revocable sessions, no URL tokens, abuse limits, transactional creation; disable unsafe provisioning until ready | Open; dry-run alerts only |
| P1-10 | Mobile/customer acceptance; 04,05,07 | Real nonempty Used and Demo journeys, images/prices/links, keyboard/AT and actual Android/iOS; offline shell cannot show current prices | Open |
| P1-11 | Release/rollback rehearsal; relevant prior gates | No known critical search/security defect, preview/production checks, recorded commit/artifacts, compatible known-good rollback | Open |

Each increment needs a focused branch/PR, appropriate tests, independent review,
updated evidence and separately verified deployment before being called live.
Eight broad product groups and A01–A15 are overlapping views, not additive counts.
No advanced scoring, new-car search or new generative feature displaces this work.

## Independent QA and customer gates

Generate cases from taxonomy, not fixed brands/stock assumptions: Used/Demo/Both ×
individual model/All models × budget absent/min/max/range/boundaries × destination,
plus compound refinements. Destination cannot silently restrict seller geography.
Unknown attributes cannot satisfy known hard constraints.

Distinguish no indexed matches, incomplete/unverified coverage, unreachable sources
and system failure. Inject timeout/403/429/parser drift, DB/index failure, worker
loss and late writes. Sold/expired/latest-negative cannot revive old cheap stock.
Test actual images, source URLs, observation times and price basis. Zero-demo
journeys prove state handling, not successful demo acquisition.

Keep warm API p95 ≤500ms and first useful results p95 ≤1s as unverified targets,
with declared India-network/workload/dataset and concurrent ingestion. Agree
sample sizes and pilot thresholds before claiming recall/identity acceptance;
publish failures and confidence limits. Measure commit-to-search lag, fresh supply,
scoped recall, source concentration, false merges, sold false positives and buyer
task success. Fixture, integration, source, deployment, benchmark and soak evidence
must stay separately labelled.

## Disagreements, constraints and dependencies

Backend/QA prioritize scan truth before more parsers; PM prioritizes missing supply
over optional AI/UI. Earlier backbone review put projection first. The new order
addresses unsafe completion assumptions first, then projection; reviewed source
work need not wait for Elastic completion. QA rejects historical green suites as
national readiness. PM rejects fluency/feature count as a substitute for inventory.

Free testing remains the owner's instruction; no paid activation. Always-on
capacity may require a later approved budget. Dealer/OEM feeds may require access
and relationships. Human-labelled independent samples, identity/availability
judgments, real devices and buyer research are external evidence dependencies.
Do not invent their results or claim near-100% national coverage.
