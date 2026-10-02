# Catalog Test Scenarios

## CATALOG-P0

### C-001 Brand list loads
Given the homepage is loaded,
when the live catalog request completes,
then the Brand dropdown contains verified brands and is selectable.

### C-002 Brand API failure
Given /api/catalog fails,
then the UI shows an explicit catalog-unavailable state and does not silently present an empty catalog.

### C-003 BMW model loading
Given BMW is selected,
then the Model dropdown loads BMW models.

### C-004 Audi model loading
Given Audi is selected,
then the Model dropdown loads Audi models.

### C-005 Mercedes-Benz model loading
Given Mercedes-Benz is selected,
then the Model dropdown loads Mercedes-Benz models.

### C-006 All Models
Given a valid brand and no model,
then the search represents all models for that brand rather than silently restricting to a subset.

### C-007 Brand change
Given BMW is selected and a BMW model is selected,
when the brand changes to Audi,
then the previous BMW model is cleared and cannot leak into the Audi search.

### C-008 Catalog normalization
Catalog navigation artifacts such as non-model labels must not appear as vehicle models.

### C-009 Refresh
A catalog refresh must not leave the dropdown disabled or stuck on a loading placeholder.

### C-010 Empty catalog
An empty catalog must produce an explicit recoverable UI state.
