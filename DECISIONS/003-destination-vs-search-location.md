# ADR 003 — Destination Is Purchase Context, Not Search Location

## Status
Accepted

## Context
The buyer may live/register a vehicle in Bengaluru while being willing to purchase in Delhi, Hyderabad, Mumbai, or another city if the overall opportunity is attractive.

## Decision
The initial destination field represents where the buyer expects to buy/register/use the vehicle. It is not an automatic inventory location filter.

The system should classify results such as:
- local
- same-state
- interstate

and later use that context for practical decision support.

## Consequences
The UI must make this distinction explicit.

Search and inventory APIs should not interpret destination as seller_city == destination_city unless the buyer explicitly selects such a restriction.

Future interstate calculations may include:
- travel/logistics
- registration/transfer considerations
- landed cost
- time/effort

Only reliable, appropriately sourced information should be presented as factual guidance.
