# Live source contribution audit — 21 October 2026

This is a dated database snapshot, not a coverage percentage or availability
guarantee. It applies the same latest-observation, active, verified, unsold,
positive-price and source-aware expiry rules as customer search.

## Finding

The registry contained 28 enabled sources labelled `live`, but only 10 supplied
eligible customer offers. Those sources supplied 5,503 offers. CarDekho, CarWale
and CarTrade supplied 5,335 (96.94%), so the apparent registry breadth did not
translate into diversified inventory.

| State | Sources |
|---|---|
| Current contributor (10) | CarDekho Used 2,099; CarWale Used 1,925; CarTrade 1,311; Mercedes-Benz Used Cars 60 demo; Fusion Cars 41; Luxury Ride 36; Motozite Demo 12; Big Boy Toyz 10; AutoBest Emperio 8; Gurudev Tata Demo 1 |
| Historical listings, none eligible (5) | 9th Gear 31; BMW Premium Selection 58; Cars24 Luxury Used 53; Motozite 15; Skoda Certified Pre-Owned 40 |
| No listing ever persisted (13) | Audi Approved Plus; AutoHangar Used Cars; Das WeltAuto; Droom; Honda Auto Terrace; Hyundai Promise; Mahindra First Choice; Maruti Suzuki True Value; OLX Cars; Quikr Cars; Spinny Luxury Used; Toyota U Trust; Volvo Selekt |

The queue does not close this gap: many sources have dozens of open jobs while
the adapter either yields no valid cards or is blocked. Observed hard failures
include HTTP 403 for Audi, Mahindra First Choice, OLX and Quikr, and a certificate
hostname mismatch for Das WeltAuto. A failed fetch is unknown coverage, never
zero market inventory.

## First restoration increment

AutoHangar was selected because its current public pre-owned page is accessible
and exposes vehicle-level cards with model, year, mileage, fuel, asking price and
image evidence. A live parser check on 21 October produced 16 distinct priced
used offers across Mercedes-Benz, BMW, Jaguar and Land Rover.

AutoHangar exposes a shared catalogue handoff rather than individual vehicle
URLs. CarScanner therefore uses a conservative title/year catalogue-card
identity, collapsing ambiguous collisions rather than inventing separate cars.
It links buyers to the original catalogue, labels that provenance in evidence,
does not assume a vehicle location, invent detail URLs or classify cards as demo.

Code validation does not make these offers customer-visible. Required rollout:

1. deploy the reviewed parser;
2. update only AutoHangar's database parser strategy;
3. run one bounded acquisition;
4. confirm canonical writes, freshness, source attribution, images and links;
5. confirm customer search returns the offers before counting the source active.

Candidate URL promotion remains behind restoration or truthful demotion of the
existing 18 zero-contribution live sources.
