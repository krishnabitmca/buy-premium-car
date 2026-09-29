# CarScanner Product Definition

## Vision
Help an Indian car buyer find the right premium used or demonstrator car wherever the deal is, while making the trade-offs of buying from another city understandable.

## Product category
CarScanner is a search and decision-support aggregator. It aggregates vehicle listings and supporting market evidence from multiple sources. It does not own inventory, negotiate on behalf of sellers, or present itself as the seller.

## Primary user problem
A buyer may know approximate car type/brand/model, budget, whether used or demonstrator is acceptable, and where they live or intend to register the vehicle. But the best available deal may be outside their city or state.

Traditional local search can hide those opportunities. CarScanner should expose them and explain the practical implications.

## Core journey
First search should be lightweight:
- Condition: Used / Demonstrator
- Brand
- Model
- Budget
- Destination / registration location

Optional refinements appear after results.

Results should help answer:
1. What cars are available?
2. Why is this car relevant?
3. Is the price interesting relative to the market?
4. How much evidence do we have?
5. Where is the vehicle?
6. What does buying it from there imply?
7. Where can I see the original listing?

## Evidence hierarchy
Prefer, where available:
1. Current original seller/listing evidence
2. Multiple corroborating sources
3. Market comparison evidence
4. Historical observations clearly labelled as historical
5. Model-level assumptions clearly labelled as assumptions

## Search geography
The default inventory search scope is India-wide.

Destination is used for context such as:
- same city
- same state
- interstate
- estimated travel/logistics implications
- registration/transfer considerations when supported by reliable data

A distance filter may exist later as an explicit user preference, but it must not silently turn destination into a hard inventory boundary.

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
- confidence

The UI should distinguish facts, derived signals, and assumptions.

## Coverage philosophy
PAN-India coverage is built incrementally.

A source is not considered covered merely because its city/category is represented in a static list. Coverage should be measurable by:
- source
- city/region
- brand/model
- listing freshness
- successful crawl rate
- deduplication/identity quality

## Non-goals
CarScanner should not initially become:
- a full dealership marketplace
- a financing platform
- an insurance marketplace
- a generic classifieds site
- a giant first-screen filter form
- a system that claims certainty when evidence is weak

## Product success signals
Early success should focus on:
- useful search completion
- relevant results per search
- source coverage
- fresh listing rate
- deduplication quality
- evidence completeness
- click-through to original listings
- engagement with cross-city opportunities

Do not optimize only for number of listings.
