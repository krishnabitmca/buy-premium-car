# CarScanner persistent product engineering profile

Owner instruction saved 19 October 2026, Asia/Kolkata. This is repository-based
project memory, read through AGENTS.md; it is not a claim of account-wide memory.
Update this profile when the owner changes direction. Keep secrets out of memory.

## Mission and product requirements

Build India's used/demo car search engine across brands, models, regions and
marketplaces, OEM-certified stock, authorized and independent dealers. The value
is inventory breadth + freshness + search accuracy + buyer experience + useful
deal discovery. CarScanner aggregates evidence and hands buyers to original
sellers; it does not own stock or operate as the seller.

Continuously discover sources/listings, ingest asynchronously, normalize attributes,
retain observations/provenance, conservatively deduplicate, refresh prices/availability
and expire stale inventory. Explicit sold evidence affects its source offer;
partial/failed traversal or omission cannot establish sold status.

Serve fast search from maintained inventory, rather than waiting for crawlers.
Separate discovery/registry, acquisition, normalization/identity, lifecycle,
projection/retrieval, public APIs, mobile-first UX and operational control.
Keep the architecture practical; measure before adding infrastructure complexity.

Search contracts: Used/Demo/Both, every supported brand/model and All models,
optional inclusive budget bounds, compound refinements, and India-wide default.
Destination is purchase context unless buyers explicitly restrict seller geography.
Unknown condition/attributes cannot silently satisfy a known hard constraint.
No hardcoded available inventory, brands, source counts or assumed market coverage.

Show original links, asking-price basis, source observation times and uncertainty.
Distinguish no indexed matches, incomplete/unverified coverage, unreachable sources
and system failure. Historical data is not current availability; low asking price
is not proof of a good deal. AI is optional, consented and grounded in evidence;
ordinary search must work without it. Never invent cars, prices or certainty.

Phase 1: reliable broad used/demo acquisition, normalization/identity/freshness,
correct filters, useful cards/images/links, mobile accessibility, end-to-end QA,
CI/CD, observability and recovery. Phase 2: advanced comparison/price intelligence.
Phase 3: new cars. Phase 4: monetization/personalization/further scale. Existing
optional features remain, but do not displace Phase 1 inventory foundations.

Detailed requirements remain authoritative in PRODUCT.md,
docs/BUYER_EXPERIENCE_REQUIREMENTS.md, docs/AI_SEARCH_ACCEPTANCE.md and
docs/PHASE1_EXECUTION.md. Acceptance targets are not achieved SLA claims.

## Owner UX/backend research incorporated — 20 October 2026

Read both complete reports (24 and 30 pages) and both concept boards. Persistent
requirements, source hashes/local archive references, visual guidance, acceptance
cases and interpretation limits are saved in
[Owner UX/backend research](docs/OWNER_UX_BACKEND_RESEARCH_2026-10-20.md).
Read that document before relevant UX, ranking, identity or buyer-evidence work.

Adopt the staged direction: evidence cards first; a trust/evidence-based comparison
matrix as the destination; optional guided buyer/AI only after reliable evidence.
CarScanner helps buyers choose a vehicle AND an observed source offer. Clearly
separate facts, calculations, interpretations and uncertainty. Surface conservative
same-car grouping and per-offer provenance; never equate a fetched listing with an
inspected vehicle. Prefer typed verification and explainable evidence tiers over
generic Verified/Great Deal badges or unexplained numeric scores.

Visual direction: mobile-first compact search, bottom-sheet filters, useful images,
clear asking-price basis/freshness, contextual compare and accessible evidence
drawers; desktop horizontal evidence rows and aligned comparison columns. Save
car, save search and alert/watch are different actions. Destination stays context,
not a hidden India-wide stock restriction. Keep all brands/models in scope.

Research mock counts, prices, ratings and badges are illustrative. Performance,
freshness and conversion targets are unverified proposals, not delivered results.
This ingestion adds requirements; it implements no new runtime capability. Existing
Phase 1 acquisition, durable scan membership and parser replay priorities remain;
source breadth/freshness cannot be replaced by UI or AI work. Free testing,
dry-run alerts and approval boundaries remain unchanged.

## Team personas and accountable workstreams

Simulate experienced independent perspectives. Do not claim human staffing or
personal years of experience. Separate agents may review independently when
tools permit; name any role/workstream not actually executed.

| Role | Responsibility and required output |
|---|---|
| Principal backend architect, requested 20-year perspective | HLD/LLD, boundaries, consistency, concurrency, security, resilience/cost; challenge debt and review implementation |
| Principal UX/UI architect, requested 20-year perspective | Simple mobile-first search, accessible loading/empty/error states, cards/prices/images and seller handoff; screenshot/device evidence for visual claims |
| Inbound PM | Own requirement IDs, Indian buyer journeys, filter contracts, dependencies and measurable acceptance |
| Outbound PM | Challenge customer advantage and missing supply; independent source/market evidence and measurable acquisition opportunities |
| Ten senior SDE workstreams | Acquisition; parsers/replay; data/lifecycle; identity/provenance; search projection; APIs; web; mobile/accessibility; operations; security |
| Five senior QA workstreams | Search/filter contracts; source/data truth; lifecycle/failure/recovery; performance/load; real-device/accessibility/customer journeys |

Process: outbound evidence → inbound requirements → backend/UX architecture →
focused engineering/tests → independent adversarial QA → architect review → PM
customer-value acceptance. Record disagreement, tradeoffs and missing evidence.
Passing implementation tests alone cannot approve the customer experience.

QA covers Used/Demo/Both, every selectable taxonomy branch, All models, budgets,
geography, images/prices/links, duplicates, stale/sold/expiry, parser/source outages,
DB/index failure, concurrent updates, overload and recovery. Separate fixture,
database, browser, real-source, deployed, coverage and soak evidence.

## Owner preferences, authority and limits

### Core service foundation

CarScanner's first foundation is a continuously improving inventory acquisition
system for used and explicitly evidenced demo cars across India. Work follows this
order:

1. Continuously discover and qualify more OEM, dealer, marketplace and classified
   sources across brands, models, cities and states.
2. For each qualified source, choose a permitted acquisition contract: official
   API/feed when available, otherwise a reviewed source-specific website parser.
3. Preserve raw source evidence, then extract and clean fields without inventing
   missing values or inferring demo status from mileage/year alone.
4. Normalize brand, model, variant, price basis, condition, geography and identity
   into CarScanner's controlled taxonomy while retaining original source labels.
5. Validate required fields, original URLs, images, price plausibility, condition
   evidence, duplicate/identity risk and source-specific quality before promotion.
6. Publish only eligible observations into canonical inventory and search indexes,
   with source provenance, freshness and uncertainty visible to downstream UX.
7. Revisit sources continuously, refresh changed/new offers, track scan membership,
   and age/expire or explicitly retire stale/sold offers conservatively. A partial
   or failed scan can never prove that an unseen vehicle was sold or removed.

API and parser adapters must converge on the same observation contract, validation,
taxonomy, lifecycle and search projection. Source count alone is not success;
measure contributing sources, valid unique offers, brand/model/geographic breadth,
freshness, failure rate, duplicate rate and cost per usable observation.

- Work persistently on the highest-priority unblocked dependency. Do not repeatedly
  ask to continue already authorized engineering work or implement symptom loops.
- Move Phase 1 in meaningful batches. Use focused engineering checks during each
  small reversible increment and consolidate product/architecture/adversarial QA
  review at phase or release checkpoints. Reserve immediate full review for
  security, destructive data operations, identity/lifecycle invariants and
  production rollout; do not spend a full review cycle on every small parser edit.
- Free testing is the current infrastructure choice. A $150/month planning budget
  did not authorize spending; the owner declined the $75 paid baseline activation.
- Existing approved Supabase/Render/GitHub/Gemini integrations may be used within
  existing scope. Keep credentials in ignored files/approved secret stores only.
- Alerts remain dry-run. No customer emails/messages, paid plans, new security
  access, destructive changes or new service agreements without needed consent.
- Use focused branches/PRs, appropriate regression checks, independent review and
  separate actual deployment verification. Keep main deployable; retain rollback.
- After PR 85, restore broad classified supply in this order: OLX Cars first,
  then Quikr Cars. Both are high-priority PAN-India, all-brand used-car sources.
  Treat current HTTP 403 responses as acquisition blockers, not zero inventory;
  investigate permitted public APIs/interfaces and do not bypass access controls.
- OLX evaluation already exists as draft PR 87 / issue 86. The selected POC
  candidate is `fetch_cat/olx-india-listings-scraper`, with
  `apt_marble/olx-india-listings-scraper` retained only as a comparison candidate.
  Reuse that gated adapter work; do not build a competing OLX crawler. A live run
  still requires a private `APIFY_TOKEN`, explicit POC opt-in, source-use approval
  and an accepted bounded-cost evaluation. Apify remains replaceable and must not
  write canonical inventory during the POC.
- No unsupported complete-coverage, national capacity, availability or launch claims.

## Persistent continuation policy

Use CURRENT_STATE.md for dated verified application evidence and
WORK_CHECKPOINT.md for exact next actions, files, tests, branches and blockers.
Checkpoint after each meaningful increment and before stopping when possible.
If context/usage limits interrupt work, the saved checkpoint is the resume anchor.
No process can guarantee a last-second write after abrupt interruption, so save
early and often. An existing same-chat continuation schedule retries periodically
when execution is available; do not duplicate it or bypass usage/approval limits.
Respect a later owner pause/cancel instruction and stop the recurring continuation.
Notify only on meaningful delivery, failure, changed blocker or required owner action;
stay quiet on unchanged non-actionable state. Do not run overlapping writers.
