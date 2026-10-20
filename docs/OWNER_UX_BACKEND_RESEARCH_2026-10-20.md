# Owner research: decision UX and backend requirements

Saved 20 October 2026. This is a synthesis of all four owner-supplied sources,
not an implementation completion report or an independently repeated product audit.
The owner requested reading and persistent profile storage. Instructions embedded
in the reports are research recommendations, not authority to deploy, spend,
expand security access, collect personal data or send messages.

## Sources and preservation

| Ref | Source | Read scope | SHA-256 |
|---|---|---|---|
| R1 | CarScanner Decision-Making UX and Backend Requirements.pdf | All 24 pages; extracted text and rendered pages | b7c0c4e94e98ed891c400e16015958f981ff74ea63bfc91ace77d66002433a41 |
| R2 | CarScanner Mobile-First Decision UX Research and Concept Report.pdf | All 30 pages; extracted text and rendered pages | 31f89f69d42a6e2356c91f2e75d38140d8223b90a6b85e3a4cf584b2374fb17f |
| V1 | CarScanner UX_UI Product Concept Board.png | Complete supplied board | d62e9da3ac854fe5b6b3303deab6bf30c5f2abfb0051b4c01283a927a141af09 |
| V2 | CarScanner Multi-Platform Car Search Experience.png | Complete supplied board | f5885d008ffe43775e95ae5a1e2b6cfc36693a7e938d4fb64aba0645d1330365 |

Original files are in `C:/Users/krish/Downloads/` under the names above. Local
preserved copies are in `../../outputs/owner-research-2026-10-20/sources/`
relative to the repository; SHA-256 and byte sizes are in the adjacent
`source-manifest.json`. Extracted text and all 54 page renders are in that same
local research directory. Full source assets have not been added to Git or
uploaded to the public repository. This tracked synthesis remains usable if
local attachments are unavailable; request the originals before claiming to
reinspect their illustrations elsewhere.

## Product direction adopted into project memory

CarScanner is the neutral decision layer above marketplaces, OEMs and dealers:
search the fragmented market, resolve supported same-car identities, shortlist,
compare evidence and trade-offs, choose an observed source offer, then hand off.
Support every brand and model across India, including used and explicitly demo
inventory. Premium-car examples do not narrow the product scope.

Use one staged product, not three separate apps:

1. **A — Evidence Cards / Scan and Shortlist:** first delivery direction. Make
   existing evidence visible through a lightweight mobile search and useful cards.
2. **B — Deal Matrix / Compare first:** destination architecture. Compare physical
   vehicles and their individual source offers with aligned evidence and trade-offs.
3. **C — Guided Buyer:** optional preference assistance on top of A/B, after data
   reliability. Deterministic search and full results remain available without AI.

The core unit is a canonical vehicle plus observed offers, comparable-market
evidence and uncertainty. Preserve four visibly separate categories: observed
fact, calculated comparison, derived interpretation, and unknown/downside.
An attractive asking price must never erase missing condition evidence.

## Requirements register

IDs below are additive traceability IDs, not substitutes for existing Phase 1
acceptance IDs. **All entries are recorded requirements requiring implementation
mapping and verification; none is marked complete by this document.** Existing
components should be reused where sound. P0/P1/P2 reflect research priorities
within the relevant workstream, not permission to displace current dependencies.

| ID | Priority | Requirement and acceptance | Provenance |
|---|---|---|---|
| UXB-01 | P0 | Preserve Used/Demo/Both, all brands/All models, optional inclusive budget bounds and compound filters. Unknown condition is explicit and cannot satisfy a known hard constraint; no frontend fallback to used or demo inference from a source name. | R1 pp4–5,12,19–21 |
| UXB-02 | P0 | Initial mobile search fits one viewport with condition, make/model, budget and destination. Advanced refinement follows results. India-wide is default; destination changes context unless the buyer explicitly restricts seller geography. | R1 pp6–9; R2 pp8–10,21 |
| UXB-03 | P0 | Mobile filters use an accessible 80–90% height/full-height bottom sheet, sticky clear/apply/result count and removable applied chips. Sort and freshness controls stay reachable. | R1 pp5–7; R2 pp9,23–25 |
| UXB-04 | P0 | Evidence cards prioritize actual image/identity, asking price and basis, comparable context, year/mileage/ownership, observation age, typed verification, source grouping and actions. Desktop uses horizontal evidence rows with source previews, not just enlarged mobile tiles. | R1 pp7–8; R2 pp8–11; V1/V2 |
| UXB-05 | P0 | Expose confirmed same-car source offers at result level. Probable matches have an explicit warning and no destructive canonical merge; similar cars remain distinct comparables; conflicts stay separate and auditable. | R1 pp9,11,14; R2 pp15–17 |
| UXB-06 | P0 | Replace generic verification with typed evidence: listing reachable, seller identified, identity confidence, provider inspection artifact, OEM certification, history/document evidence and explicit seller availability confirmation. Fetch success is not vehicle inspection. | R1 pp5,11–13; R2 pp7–8 |
| UXB-07 | P0 | Server supplies per-offer observation timestamps, freshness state/TTL and uncertainty. Latest observations win; explicit negative evidence blocks older positive evidence. Partial/failed scans or absence never mean sold or zero market stock. | R1 pp11–17,20 |
| UXB-08 | P0 | Deterministic, versioned ranking applies hard eligibility first, then calibrated evidence dimensions. Return reason/watch-out codes and verbal evidence tiers. Price reference includes cohort size, confidence and methodology; insufficient evidence abstains. No unexplained 92/100 score or guaranteed saving. | R1 pp12–14; R2 pp13–18 |
| UXB-09 | P0 | Contextual compare tray appears after selection; after two candidates comparison is prominent. Evidence drawers explain both advantages and risks with visible provenance and original source links. | R1 pp7–9,19; R2 pp10,14–18 |
| UXB-10 | P0 | Instrument privacy-conscious search → evidence → compare/save/watch/handoff progression. Distinguish zero indexed matches, partial coverage, unreachable source and system failure. Measure source concentration and demo coverage alongside UX. | R1 pp15–18,21–22; R2 pp26–28 |
| UXB-11 | P1 | Full comparison supports 2–3 mobile candidates with pinned headers/stacked sections and 3–4 desktop aligned columns. Compare asking price, reference gap, usage, freshness, evidence, offers and geography. Missing fields are unknown, not zero. End with explainable trade-offs, not a command. | R1 pp8–9,19–20; R2 pp14–18 |
| UXB-12 | P1 | Retain observations for auditable price history/change events. Separate save car, save search, watch price and alert subscription. Server watches persist normalized intent and re-evaluate current inventory, not a stale search response. Channels require separate consent and operational readiness. | R1 pp12,15,19,22; R2 pp11,24,28 |
| UXB-13 | P1 | Stable cursor/keyset pagination uses ordered ranking tuple plus stable vehicle ID with snapshot/inventory revision; no duplicates/omissions on an unchanged snapshot. Any revision policy is explicit. | R1 pp12,14,20,22 |
| UXB-14 | P1 | Image metadata captures dimensions, role, source, quality/fallback, checksum/perceptual hash and source policy. Rights-aware thumbnail/proxy decisions, reserved aspect ratio, useful alt text, gallery only on demand. No fabricated photo for missing inventory media. | R1 pp14–15,22; R2 pp25–26; V1/V2 |
| UXB-15 | P1 | Keep source quality measurable and private until calibrated: traversal/recheck success, freshness, availability consistency, discrepancy and explicit negatives. Distinguish source reliability from vehicle condition. Cross-city costs are explicit estimates separate from asking price. | R1 pp16–17,22; R2 pp17,24 |
| UXB-16 | P2 | Guided buyer captures must-have/nice-to-have/avoid and hard versus soft preferences. Optional natural language requires consent and editable interpretation before execution; deterministic fallback and See all remain. Why it fits and Watch-outs have equal weight. | R1 pp9–10,19–22; R2 pp18–23 |
| UXB-17 | P2 | Incremental search projection/outbox follows demonstrated PostgreSQL parity and measured need; PostgreSQL remains canonical. Shared/family shortlists are later research scope requiring security/product design. | R1 pp10–14,22; R2 p24 |

## Backend contract and boundaries

Extend rather than replace sound current domain components. A search result should
make the following server-owned evidence available:

- Canonical vehicle/group ID, attributes with explicit unknowns, condition;
  identity state, match reasons/evidence and matcher version.
- `best_offer` and `offers[]`: listing/source IDs, original URL, asking price and
  price basis, observation time, freshness and availability evidence per offer.
- Market reference: cohort definition, comparable count, median/percentile,
  price gap, confidence and methodology version. Form the comparison cohort before
  buyer-specific refinements that could distort the reference population.
- Typed verification evidence with provider, observation time and expiry;
  versioned ranking tier, reason codes and watch-out codes.
- Stable paging token and revision/snapshot contract.

Potential additions are identity evidence/links (confirmed, probable, possible,
conflicting), verification evidence, image assets, market-reference/cohort data,
private source-quality metrics, buyer search/watch intent and telemetry. These are
design requirements, not a claim that all tables exist. Record identity inputs and
merge/split decisions for audit; never duplicate core rules in the frontend.

Vehicle facts, offers, evidence and history may be separate logical resources
served initially by the same handler. Do not require a microservice rewrite.
Cache proposals: internal result computations 30–60 seconds keyed by normalized
intent plus inventory revision; catalog 5–15 minutes; detail by revision. Reconcile
these with actual invalidation/freshness before adoption. Do not serve offline or
browser-cached inventory as current availability, or cache personal watch APIs.

## Visual reference and responsive behavior

V1/V2 supply visual direction: white/light-blue surfaces, navy text, clear blue
primary actions, rounded cards, legible prices and actual car photography.
Mobile journeys: home/search → results → bottom-sheet refinements → vehicle
dossier/gallery → compare → save/alerts; map view is an optional geographic lens.
V2 includes contextual bottom navigation and a photographic hero. Keep the first
search fast and compact rather than blindly reproducing a large hero.

Use behavior-based layouts: compact phone below 480px, larger phone 480–767px,
tablet 768–1023px, persistent desktop filters/evidence rows at 1024px and above,
bounded content width at 1440px and above. Mobile comparison stacks evidence;
desktop aligns columns. Map prices need genuine location/offer evidence and a
list alternative; maps cannot imply comprehensive national coverage.

The PDFs qualify the boards: generic green Verified/Great Deal badges, comparison
grids squeezed into phones, premium-only imagery and three-column desktop cards
are not requirements to copy literally. Prefer typed evidence, calibrated verbal
tiers and horizontal desktop rows. Mock BMW/Mercedes inventory, ratings, source
counts, savings, timestamps and on-road labels are illustrations, not live facts.
Never relabel an asking price as on-road without source evidence.

## Accessibility, performance and measurement acceptance

Target practical 44 CSS-pixel controls, text/icon status independent of color,
visible keyboard focus, modal focus containment, Escape/close and focus return,
restrained live result-count announcements, useful image alternatives, 320px
reflow and usable 200% text resizing. Validate contrast and screen-reader flows;
concept images are not accessibility evidence.

Research-proposed performance targets, not measured current results: first
meaningful results within 2 seconds on representative mid-tier mobile/4G;
LCP ≤2.5s, INP ≤200ms and CLS ≤0.1 at p75, measured separately by device class.
Load viewport thumbnails plus modest look-ahead, preserve layout dimensions,
avoid lazy-loading LCP imagery; defer galleries/evidence/history and consider
compare prefetch after selection. Perceived filter response below 500ms is a
proposed goal, not a current promise.

North star: **Evidence-backed Decision Progression Rate** — qualified search
sessions that review meaningful evidence and then compare, save/watch or hand off
to a source. Operationalize qualification and evidence sufficiency before using
the metric. Also measure useful/zero results, reformulation, latency, time to
shortlist/two-car compare, completion, evidence/coverage engagement, stale/price
reports, multi-source group use, duplicate inflation avoided, and consented
watch retention. Raw inventory/pageview counts alone are insufficient.

Event families: search started/submitted/rendered; filter opened/applied and sort;
vehicle impression/open; evidence/verification/history/coverage opens; duplicate
group expansion/source selection; compare add/remove/open/complete; car/search
save and alert creation/open; original-source click; stale/price mismatch report.
Use pseudonymous session/query/vehicle IDs, position, parsed filters, device class,
source count, identity confidence, age, comparable count and experiment assignment.
Minimize personal data, avoid raw natural-language/contact text, define retention,
and keep telemetry asynchronous. This does not authorize a new tracking service.

Private coverage dashboard requirements: eligible offers separately from canonical
vehicles; contributing sources, top-one/top-three concentration, multi-source
rate, condition distribution, brand/model/city matrix, media coverage, age buckets,
traversal completeness, queue age and explicit negative observations.

Proposed observation-age objectives: high-volume marketplace/API p95 ≤2h;
OEM/certified/demo ≤4h; long-tail dealer ≤12h. After 24h, indicate aging/last seen
and never imply confirmed availability. TTL/expiry is source-specific. These are
planning objectives requiring measured acquisition capacity, not an achieved SLA
or a reason to loosen current lifecycle rules.

## QA and delivery reconciliation

Keep the existing Phase 1 dependency order: durable scan membership and sanitized
parser replay (P1-02), reliable acquisition/refresh and broader accessible sources
remain immediate work. Source breadth and freshness must progress alongside the
decision UX; a new interface cannot cure missing demo inventory. AI/UI additions
must not displace these foundations or reactivate blocked sources.

When prerequisites permit, deliver focused slices: evidence semantics/ranking
reasons/telemetry → mobile search/filters/cards/contextual compare → conservative
result-level source grouping → full comparison → price history/server watches →
calibrated source/inspection integrations → optional guided buyer. Measure and
verify each slice; no blanket rewrite or simultaneous three-concept build.

Required end-to-end cases include brand + All models, Demo + all brands without
a query, sparse supply disclosure, one/two-sided budgets, compound filters,
confirmed/probable/conflicting identities, latest sold/negative precedence,
failed/incomplete traversal, insufficient comparables, stale cheap offers,
unknown condition, missing images/fields, stable paging ties, interstate context,
AI rejection/outage/editable interpretation, save versus alert distinction,
offline freshness, keyboard/modal navigation and attributed source handoff.
Use fixture, DB/API, browser, actual source, production and real-device evidence
as separate gates. This research ingestion runs none of those implementation gates.

R2 proposes experiments on market-context placement, verbal versus numeric deal
signals, contextual compare, exact age versus age buckets, collapsed versus inline
offers, evidence ordering, 3 versus 4 compare columns and guided shortlist size.
Measure comprehension, qualified progression and downstream backtracking, not
clicks alone; segment novice, model-decided and expert buyers. Test perceived
neutrality and user understanding of why a vehicle ranked highly.

## Interpretation limits and unresolved decisions

- The reports' current-product audits and dated inventory totals are source claims,
  not a fresh verification here. Their 6,598 used/119 demo/38 unknown/12 sources
  baseline counts source offers, not unique cars or national recall. Refer to
  CURRENT_STATE.md for dated verified implementation evidence.
- External competitor/research citations have not been independently revalidated
  during ingestion. Conversion uplifts (A 4–8%, B 8–15%, C 6–12%) are explicitly
  hypotheses, not outcomes. Directional estimates (A 8–12 engineering person-weeks,
  B 16–24, C 20–32; calendar 4–6/8–12/10–14 weeks with parallel staffing) are not
  delivery commitments or evidence of actual team staffing.
- Screens showing sign-in, alerts, call/WhatsApp, shared comparisons, seller
  ratings, verification or map pins do not authorize customer messages, identity
  access expansion, paid integrations or new assurances. Alerts remain dry-run.
- Anonymous device saves and consented server watches are distinct. Authentication,
  inspection/history partners, media rights, estimated acquisition costs, calibrated
  ranking/source quality and freshness capacity each need focused implementation
  decisions and tests before corresponding claims are exposed.
- This is repository-based project memory, not an account-wide or plugin-wide
  memory update. Existing product invariants and approval boundaries still apply.
