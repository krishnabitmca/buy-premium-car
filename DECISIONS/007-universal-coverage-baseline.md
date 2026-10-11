# ADR 007 — Brand-independent acquisition and explicit source coverage

Accepted as an incremental correction to background acquisition (ADR 006).

BMW and Mercedes searches are examples, not a coverage boundary. Schedule an
India-wide baseline for every concrete brand in the database registry as well
as global and customer-demand jobs. Every enabled source with a verified adapter
and matching brand/all capability is eligible. Customer demand increases urgency;
it must not be the only way a brand enters acquisition. Unverified sources remain
outside execution and must be visible as coverage gaps.

Return the complete applicable source plan to customers, without a top-N display
cutoff. Show whether a source has matching observations loaded, has no established
coverage in those observations, or lacks an inventory adapter. These states do
not establish catalogue completeness or that a source has no cars. Loading more
pages updates represented sources. Even all sources having observations does not
prove exhaustive coverage.

This increment does not establish all-brand or all-marketplace readiness. The
registry taxonomy is incomplete, bounded scans need durable continuation, and
source verification and physical-car identity matching remain launch gates.
Success must be assessed across a brand × source × region matrix with scan depth,
freshness and extraction accuracy, not a two-brand listing-count increase.
