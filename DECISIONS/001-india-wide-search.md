# ADR 001 — India-wide Search by Default

## Status
Accepted

## Context
A buyer in Bengaluru may find a materially better premium-car deal in another Indian city or state. Restricting inventory to the buyer's local geography would hide potentially useful opportunities.

## Decision
CarScanner searches the available inventory across India by default.

Destination is retained as buyer context and may affect ranking, explanation, or downstream purchase calculations.

## Consequences
Positive:
- broader opportunity discovery
- supports interstate buying naturally
- avoids hard-coding state/city boundaries into the core search

Trade-off:
- results must clearly communicate vehicle location and practical implications
- future landed-cost and logistics intelligence becomes important

## Guardrail
A destination field must not silently become a geographic inventory filter.
