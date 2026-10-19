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

- Work persistently on the highest-priority unblocked dependency. Do not repeatedly
  ask to continue already authorized engineering work or implement symptom loops.
- Free testing is the current infrastructure choice. A $150/month planning budget
  did not authorize spending; the owner declined the $75 paid baseline activation.
- Existing approved Supabase/Render/GitHub/Gemini integrations may be used within
  existing scope. Keep credentials in ignored files/approved secret stores only.
- Alerts remain dry-run. No customer emails/messages, paid plans, new security
  access, destructive changes or new service agreements without needed consent.
- Use focused branches/PRs, appropriate regression checks, independent review and
  separate actual deployment verification. Keep main deployable; retain rollback.
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
