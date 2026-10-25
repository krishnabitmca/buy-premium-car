# Three-agent delivery model

The workflow `.github/workflows/three-agent-delivery.yml` is a **gated coordination
skeleton**, not three autonomous Codex processes. Do not report it as agents
running independently.

## Agent 1 — implementation
Work in an isolated branch, document the source contract, write parser fixtures,
unit tests and customer-search E2E coverage, and open a PR. The workflow pins the
exact PR commit to prevent reviewing a different revision.

## Agent 2 — independent reviewer
A different GitHub identity reviews that exact commit and posts an APPROVED
review. Review data must be current and independent. If code changes, review
again. Inspect extraction permissions, partial scans, normalization, image
provenance, deduplication, false-sold protections, and CI failures.

## Agent 3 — release coordinator
Check the pinned SHA and required GitHub checks. Never deploy a draft, an
unreviewed PR, or a failing commit. The workflow currently **does not merge or
deploy**. GitHub branch protection, deployment environment approvals, dedicated
least-privilege identities and deployment verification must be configured before
turning on automated release actions.

## Invocation
Run `CarScanner Three-Agent Delivery` manually with `pr_number` and
`deploy=false`. A green run confirms the declared gates, not production health.

## Production acceptance
After an authorized merge, verify the exact commit on Render, successful
startup, an actual inventory refresh, structured extraction diagnostics, and
fresh eligible unique vehicle counts. Do not infer inventory absence from an
empty or failed extraction. Roll back on buyer search regressions.

## Follow-on work
Integrate three genuinely separate Codex worker identities/runtimes through a
secure orchestration service, GitHub App, or approved external runner. Each
worker needs scoped credentials, a bounded job, auditable output, and a
human-approved deployment policy. This repository change does not provision
such runtimes or credentials.
