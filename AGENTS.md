# CarScanner AI Development Instructions

## Persistent team profile and continuation memory

At the start of every CarScanner session or scheduled continuation, read
CARSCANNER_PROFILE.md, CURRENT_STATE.md and WORK_CHECKPOINT.md before choosing work.
Follow the team review responsibilities and product mandate in the profile.
For UX, buyer evidence, ranking or identity work, also read
docs/OWNER_UX_BACKEND_RESEARCH_2026-10-20.md, the owner research requirements
linked from the profile. Research priorities do not displace Phase 1 dependencies.
Refresh state/checkpoint after meaningful work and before stopping. Saved state
is dated evidence, not proof of current deployment or inventory; verify changes.
Continue the highest-priority unblocked Phase 1 dependency without asking for
permission already granted. Preserve unfinished user changes. No paid activation,
credential expansion or outbound customer messages without required authorization.
Checkpoint before usage/context exhaustion when possible; rely on the existing
continuation schedule rather than creating duplicate reminders on every stop.

## Before changing code
Read:
- PROJECT_CONTEXT.md
- PRODUCT.md
- ARCHITECTURE.md
- ROADMAP.md
- CHANGELOG.md
- relevant DECISIONS/*.md

Then inspect the current implementation and tests.

## Product invariants
Never casually change these:
- CarScanner is an aggregator, not a marketplace.
- Search is India-wide by default.
- Destination is not an automatic inventory boundary.
- Out-of-city cars can be valid results.
- Distance is context unless explicitly made a hard constraint.
- Historical data is not proof of current availability.
- Asking price is not proof of deal quality.
- Preserve source attribution and original listing URLs.
- Do not overwhelm the first search screen with every possible filter.
- Expand source coverage incrementally.

If a proposed change conflicts with an invariant, stop and document a new product/architecture decision before implementing it.

## Change strategy
Prefer the smallest change that solves the requested problem.
Do not rewrite working backend/data pipelines for a front-end request.
Do not duplicate domain rules in multiple layers.
Prefer additive API/data changes and backward compatibility.

## Git workflow
- Create a feature branch from main.
- Make focused changes.
- Update documentation when behavior or architecture changes.
- Run relevant tests/verification.
- Open a pull request.
- Review the diff.
- Merge only after verification.
- Keep main deployable.

## Deployment discipline
GitHub state and Vercel state are separate.
Never state that production is updated unless deployment has been verified.
Use preview deployment/verification before production whenever available.

## Completion checklist
- [ ] Product behavior matches PRODUCT.md
- [ ] Architecture boundaries remain intact
- [ ] Relevant tests/verification pass
- [ ] Source links/provenance are preserved
- [ ] Documentation is updated if needed
- [ ] PR diff is focused
- [ ] Deployment status is actually verified

## New AI session rule
Treat the repository as the durable source of truth. Re-read the project context before relying on conversational memory.

If the requested work is ambiguous, preserve existing behavior and ask/clarify rather than inventing a new product direction.
