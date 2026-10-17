# ADR 013 — Inventory breadth through used-model evidence and traversal

New-car catalogues cannot define used-car acquisition: discontinued families must
remain discoverable. Learn source-evidenced model families from CarDekho/CarTrade
listing cards and CarWale's advertised national used-model category links. Retain
the original evidence URL and source-advertised stock count separately from our
indexed inventory. Counts are source claims at discovery time, not verified stock.

Create India-wide model jobs across enabled, verified, reviewed adapters with
configured model routes. Use the existing durable queue and its uniqueness key;
do not promote model-discovery evidence into verified model capability or inventory.
Rescheduling completed model jobs respects source freshness targets. Rediscovery
must preserve running/partial/failed jobs and their pagination checkpoints.
Bootstrap from stored family observations, including discontinued models; historical
evidence identifies a model only. Current listings still require fresh acquisition.

Reserve the existing ten-job quarter-hour budget as three general jobs, four
source-discovered model jobs, and three pending traversal jobs. Run all three
classes even if another fails, then fail the workflow if any class failed.
This prevents discovery fan-out from consuming every traversal slot. Daily brand
scans and source health/retry/claim fences remain intact. Free-tier capacity is
bounded and does not establish catalogue completeness or a national freshness SLA.

Add CarTrade's reviewed national listing-card adapter, preserving observed family,
card-local asking price, mileage, year, city, image and individual listing URL.
Follow advertised pagination only. Targeted marketplace scans replace the generic
root endpoint so the next batch can spend its budget on the advertised next page,
preserving distinct endpoints. The national sources expose multiple cities already;
do not multiply work by guessed city URLs or conflate destination with
acquisition geography. City-only adapters remain a separate validation gate.

Extend the operational audit with source/brand/model traversal state and discovery
evidence. No customer UI redesign or historical-availability fallback is introduced.
