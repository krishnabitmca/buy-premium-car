# Search Test Scenarios

## Core journeys

- S-001 Audi + All Models + Used
- S-002 BMW + All Models + Used
- S-003 Audi + Demo
- S-004 Audi + Used + Demo
- S-005 BMW X5 + ₹30–40L
- S-006 Mercedes C-Class + Used
- S-007 BMW + ₹5–10L
- S-008 Audi + ₹30L+
- S-009 Toyota + Used
- S-010 No brand + budget only
- S-011 Interstate search with Bengaluru destination
- S-012 Invalid minimum greater than maximum
- S-013 Zero-result combination

## Invariants

For every returned result:

- Brand/model must match the requested search.
- Condition must match the requested condition.
- Price must satisfy min/max when supplied.
- Destination must not incorrectly become an inventory geography boundary for India-wide search.
- Source status must preserve source identity.
- A failed source must not remove successful results from other sources.
- Duplicate vehicles should be consolidated according to the deduplication contract.

## Search modes

Verify the UI and API consistently handle:

- inventory
- inventory_partial
- live_coverage_fallback
- live_fallback
- live
