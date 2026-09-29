# ADR 002 — CarScanner Is an Aggregator, Not a Marketplace

## Status
Accepted

## Context
The product's value comes from discovering and comparing listings across sources while preserving the original seller relationship.

## Decision
CarScanner is a search/decision-support aggregator.

The original seller/source remains the source of truth for the listing. CarScanner should preserve source attribution and original listing links.

## Consequences
Positive:
- broad source coverage is possible
- no need to own or transact inventory
- evidence/provenance can be a core differentiator

Trade-off:
- listing freshness and source reliability become critical
- availability cannot be claimed beyond the evidence observed

## Guardrail
Do not design the product as if CarScanner owns, guarantees, or sells the vehicle unless a future explicit business decision changes this ADR.
