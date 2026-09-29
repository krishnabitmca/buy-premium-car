# ADR 005 — Customer Search Must Be Live

## Status

Accepted

## Decision

The customer-facing CarScanner search experience must use live marketplace/source responses at search time.

The repository snapshot data/latest.json may continue to exist for historical analysis, reports, development fixtures, and crawler output, but it must not be the source of truth for a customer search.

If live marketplace queries fail, CarScanner should clearly show that live search is unavailable. It must not silently substitute stale/offline inventory.

## Consequences

The live search layer must:
- expose source-by-source status
- record when the observation was made
- preserve original source URLs
- tolerate individual source failures
- make source coverage visible
- distinguish current observations from historical data

This makes live source reliability, rate limiting, anti-bot behavior, parsing resilience, and response time first-class engineering concerns.

## Guardrail

"Live" means the request attempts to obtain current data from the configured live source. It does not mean the source guarantees that every listing is updated at the exact second of the request.
