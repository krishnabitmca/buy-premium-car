# ADR 008 — Fast indexed search with grounded AI

Status: accepted target architecture from the product owner's direction;
implementation incomplete. Supersedes ADR 005's request-time acquisition
requirement for the target customer experience, not its provenance/freshness rules.

## Decision

Serve customer search from a continuously maintained canonical inventory index.
Discovery, page traversal, extraction and refresh execute in background workers.
Missing/stale coverage schedules work and remains visible; customer responses do
not wait for live marketplace crawling. Existing legacy/live fallback behavior
must be migrated and verified before claiming this decision is implemented.

AI interprets intent, retrieves relevant alternatives and explains comparisons
using indexed listing evidence. Typed backend constraints remain authoritative.
AI cannot create inventory facts or substitute its own price for a source offer.
Simple searches must remain usable when AI is unavailable, and optional AI
explanations must not block first results. No provider or paid plan is selected
by this architectural decision.

Keep PostgreSQL as the canonical inventory store. Introduce additional search or
vector infrastructure only when measurements and retrieval requirements justify
it. The search projection, query indexes, connection handling and bounded metadata
cache should be evaluated before adding services. Never cache past freshness
limits, hide sold evidence or broaden access to user/private data for speed.

## Validation

Use docs/AI_SEARCH_ACCEPTANCE.md for latency, coverage, AI grounding, whole-result
filtering, mobile and deployment gates. All-brand and source completeness require
measured acquisition evidence; neither AI fluency nor passing fixture tests is
proof that the customer's market options have been discovered.
