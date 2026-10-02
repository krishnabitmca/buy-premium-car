# Source and Resilience Scenarios

## Source applicability

Verify:

- BMW Used -> applicable used sources
- Audi Used -> applicable used sources
- Mercedes-Benz Used -> applicable used sources
- Audi Demo -> applicable demo sources
- Audi Used + Demo -> union of applicable verified sources
- Candidate/unverified sources never execute

## Source isolation

- One source timeout
- One source HTTP error
- One source parser error
- One source circuit open
- Multiple source failures
- All sources unavailable

Expected behavior:

- Successful sources continue to contribute results.
- Failed source status remains visible in diagnostics.
- One source failure does not fail the whole search unless the contract explicitly requires a source.
- Circuit breaker state changes according to policy.

## Inventory coverage

Verify:

- Complete inventory coverage -> inventory-first path may be used.
- Partial inventory coverage -> live coverage fallback is used when enabled.
- Destination does not reduce India-wide source coverage.
- Stale inventory does not masquerade as current complete coverage.

## Deduplication

The same vehicle observed on multiple sources must not create duplicate customer cards when the deduplication contract says they represent the same vehicle.
