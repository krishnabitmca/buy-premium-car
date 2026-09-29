# ADR 004 — CarScanner Is a Cross-Marketplace Price Comparison System

## Status

Accepted

## Decision

CarScanner's primary customer value is to discover the **lowest and best possible rate** for used and demonstrator cars across multiple automotive marketplaces and seller sources.

The system should:
- aggregate listings from multiple sources
- identify when multiple listings represent the same vehicle where evidence permits
- compare observed asking prices
- provide market/reference context
- surface the lowest observed comparable price
- provide a separate evidence-based deal signal for the strongest price opportunity
- link back to the original marketplace/seller listing

## Important distinction

"Lowest listed price" is an observed comparison.

"Best possible rate" is a derived decision-support signal and is never a guarantee of the final negotiated transaction price.

## Consequences

The product architecture must increasingly prioritize:
- cross-source vehicle identity
- deduplication
- price normalization
- listing freshness
- variant/trim normalization
- evidence quality
- comparable-vehicle matching

This becomes a core product capability rather than a secondary feature.

## Guardrail

Do not claim that CarScanner has found the absolute lowest price in India unless the available source coverage justifies that claim.

Use language such as "lowest price found" or "lowest observed price" when coverage is incomplete.
