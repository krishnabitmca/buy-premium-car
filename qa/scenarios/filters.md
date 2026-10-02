# Filter Matrix

## Visible filters

### Condition
- Used
- Demonstrator
- Used + Demonstrator

### Price
- No minimum / no maximum
- Minimum only
- Maximum only
- Exact boundary
- Range
- Minimum greater than maximum
- Zero
- Decimal lakh values

### Fuel
- Petrol
- Diesel
- Electric
- Hybrid
- Multiple fuels
- Clear fuel filter

### Seller location
- All India
- Bengaluru
- Another observed city
- City with zero matching results

### Age
- Any age
- <=2
- <=3
- <=5
- <=7
- Boundary year
- Missing year

### Destination
- Bengaluru
- Different Indian city
- Destination must remain purchase/register context, not an India-wide inventory boundary.

### Sort
- Recommended
- Lowest price
- Best market gap
- Lowest mileage
- Newest

### Quick filters
- All
- Petrol
- Diesel
- Electric
- Hybrid
- SUV
- Sedan

## Interaction coverage

At minimum test:

- Condition × brand
- Brand × model
- Brand × price
- Brand × fuel
- Brand × age
- Brand × city
- Price × fuel
- Price × age
- Fuel × age
- City × destination
- Condition × price × age
- Brand × model × price

Do not attempt a naive full Cartesian product. Use pairwise coverage, high-risk three-way combinations, boundaries, and representative end-to-end journeys.

## Invariants

Filtering must never:

- return an out-of-range price;
- return the wrong fuel when fuel is selected;
- return an older vehicle than the selected age;
- retain an invalid model after a brand change;
- convert destination into a hard inventory boundary;
- leave stale filters after Clear All.
