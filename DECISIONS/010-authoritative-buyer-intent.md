# ADR 010 — Authoritative buyer intent and optional Gemini pilot

Status: implementation in progress; production enablement requires verification.

Normalize form and model output through one bounded, typed intent. PostgreSQL
applies hard constraints and deterministic ordering before pagination. Unknown
constrained attributes do not match. Destination remains purchase context; seller
city is an explicit optional boundary. UI refinements must request a new result
set rather than filter the first loaded page. Preserve backward-compatible
library defaults for background consumers.

Elasticsearch v1 cannot represent these additional constraints or ranking. Route
advanced requests to PostgreSQL until projection parity is implemented and tested.
Never filter an Elasticsearch page and present its unfiltered total as correct.

Gemini is an optional, opt-in interpretation service, never an inventory source.
The owner approved a free-tier key, stored only in ignored local configuration
and Render, no billing, and an initial 30-call daily app limit. Free-tier prompts
may improve Google's products. Explain that before consent; reject contact and
private-document input. Keep the feature disabled until provider generation,
distributed quota, typed validation and browser flows pass verification. Provider
failure must preserve ordinary search, without silently dropping constraints.

Coverage expansion, semantic retrieval, reliable valuation, saved-watch delivery,
native applications and national capacity remain separate measured launch gates.
