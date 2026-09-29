# CarScanner Product Definition

## Product name

**CarScanner**

CarScanner is the system name and customer-facing product name.

## Core promise

**Find the lowest and best possible rate for a used or demonstrator car across the marketplaces where that vehicle is listed.**

CarScanner should query available automotive marketplaces and seller sources live at search time, identify comparable vehicles, and help the buyer understand which listing represents the strongest price opportunity based on available evidence.

"Lowest price" and "best possible rate" must be treated as evidence-based concepts, not absolute guarantees. CarScanner can only compare the inventory and evidence it has discovered.

## Vision

Help an Indian car buyer find the right premium used or demonstrator car wherever the deal is, with the strongest available price intelligence across marketplaces and clear understanding of the trade-offs of buying from another city.

## Product category

CarScanner is a **vehicle search, price-comparison, and decision-support aggregator**.

It aggregates vehicle listings and supporting market evidence from multiple sources. It does not own inventory, negotiate on behalf of sellers, or present itself as the seller.

## Primary user problem

A buyer may know:
- approximate car type/brand/model
- budget
- whether used or demonstrator is acceptable
- where they live or intend to register the vehicle

The same or similar vehicle may be listed on multiple marketplaces, by dealers, or through other seller sources at different prices.

The buyer should not have to manually search every marketplace to determine:
- where the vehicle is listed
- what the asking prices are
- whether the listings represent the same vehicle
- which asking price is lowest
- whether the lowest asking price is actually a strong deal
- whether a cheaper vehicle in another city/state is worth considering

CarScanner exists to perform that comparison.

## Core customer journey

First search should be lightweight:
- Condition: Used / Demonstrator
- Brand
- Model
- Budget
- Destination / registration location

Optional refinements appear after results.

The first result experience should prioritize:
1. Lowest comparable price
2. Best price opportunity based on evidence
3. Market/reference price
4. Vehicle location
5. Vehicle age, mileage, ownership and variant
6. Number and quality of corroborating sources
7. Local vs interstate purchase context
8. Original marketplace/seller listing

## Lowest price vs best deal

These are deliberately different concepts.

### Lowest listed price

The lowest observed asking price among comparable vehicles currently discovered by CarScanner.

This is a factual comparison subject to:
- inventory coverage
- listing freshness
- vehicle identity accuracy
- variant/condition differences

### Best possible rate

The strongest price opportunity CarScanner can identify after considering relevant evidence such as:
- comparable market prices
- vehicle age
- mileage
- ownership
- exact variant/trim
- condition/evidence
- source corroboration
- price history where available
- seller/source quality
- location and potential interstate costs
- confidence in vehicle/listing identity

CarScanner must not present a derived "best rate" as a guaranteed final transaction price.

## Marketplace comparison

A core capability is **cross-marketplace comparison**.

When the same vehicle appears on multiple sources, CarScanner should attempt to identify the canonical vehicle and group its listings.

For example:

| Vehicle | Marketplace A | Marketplace B | Marketplace C |
|---|---:|---:|---:|
| Same identified vehicle | ₹38.50L | ₹37.75L | ₹39.00L |

The buyer should be able to see that ₹37.75L is the lowest observed listing for that identified vehicle, rather than treating the three listings as three independent cars.

If identity cannot be established confidently, CarScanner should compare them as comparable vehicles and clearly label the confidence.

## Search geography

The default inventory search scope is India-wide.

Destination is used for context such as:
- same city
- same state
- interstate
- estimated travel/logistics implications
- registration/transfer considerations when supported by reliable data

A distance filter may exist later as an explicit user preference, but it must not silently turn destination into a hard inventory boundary.

A better deal in another city must remain discoverable.

## Evidence hierarchy

Prefer, where available:
1. Current original seller/listing evidence
2. Multiple marketplace listings for the same vehicle
3. Multiple corroborating sources
4. Market comparison evidence
5. Historical observations clearly labelled as historical
6. Model-level assumptions clearly labelled as assumptions

## Deal interpretation

A lower asking price does not automatically mean a better deal.

Deal intelligence may consider:
- comparable market prices
- vehicle age
- mileage
- ownership
- trim/variant
- source corroboration
- condition/evidence
- price history when available
- seller/source quality
- location and potential acquisition cost
- confidence

The UI should distinguish:
- **Observed fact**
- **Calculated comparison**
- **Derived deal signal**
- **Assumption**

## Coverage philosophy

PAN-India coverage is built incrementally.

CarScanner should measure coverage by:
- marketplace/source
- city/region
- brand/model
- listing freshness
- successful crawl rate
- vehicle identity quality
- deduplication quality

CarScanner must never imply complete PAN-India marketplace coverage if only a subset of sources has been indexed.

## Product boundaries

CarScanner should initially remain focused on:
- used cars
- demonstrator cars
- cross-marketplace discovery
- price comparison
- vehicle/deal evidence
- buyer decision support

It should not initially become:
- a full dealership marketplace
- a financing platform
- an insurance marketplace
- a generic classifieds site
- a giant first-screen filter form
- a system that claims certainty when evidence is weak

## Product success signals

The most important early signals are:
- percentage of searches returning useful comparable vehicles
- percentage of vehicles with multiple source observations
- lowest-price discovery rate
- cross-marketplace match/deduplication accuracy
- listing freshness
- price-comparison accuracy
- evidence completeness
- click-through to original marketplace/seller
- engagement with cross-city opportunities

Do not optimize only for the number of listings.

## Product principle

**CarScanner should reduce the work of searching many marketplaces into one evidence-backed car-price comparison experience.**
