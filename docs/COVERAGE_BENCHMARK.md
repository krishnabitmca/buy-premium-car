# Sampled source coverage benchmark

Use a source-side sample collected independently of CarScanner results/parsers.
Record its exact source, scope, review time and eligible/ineligible labels. Sample
multiple sources, brands/models, regions and used/demo conditions for meaningful
evaluation. A convenient one-page dealer sample is a smoke check only.

Input shape (illustrative placeholder, not a real inventory observation):

```json
{
  "version": 1,
  "sampling": {
    "method": "manual_source_review",
    "reviewer": "reviewer-pseudonym",
    "scope": "Describe selected source pages, sampling method and exclusions",
    "collected_at": "REPLACE_WITH_CURRENT_TIME_AND_UTC_OFFSET"
  },
  "records": [{
    "source": "Exact registered source name",
    "url": "https://example.invalid/individual-stock?id=123",
    "brand": "BMW",
    "model": "X1",
    "seller_state": "Delhi",
    "condition": "used",
    "eligible": true
  }]
}
```

Use source-backed used/demo labels, not an inference from certification or
unregistered status. Label explicit sold cards `eligible: false` and retain the
reason. State labels describe the declared sample strata, not proof of physical
vehicle location. Model labels must use the reviewed canonical representation;
brand/model/condition disagreements are reported as attribute mismatches.

With server database configuration loaded securely:

```sh
python -m src.coverage_benchmark --sample private-review.json --output private-benchmark.json
```

The CLI reads canonical PostgreSQL directly and requires no model or paid service.
It does not fetch sampled URLs, activate feeds or enqueue crawling. Keep review
artifacts private and never put credentials, buyer data or reviewer contact details
in them. Source URLs themselves must not contain credentials.

Reports distinguish missing URLs, attribute mismatches and source-reviewed
ineligible listings that remain searchable. Recall counts eligible sampled source
offers, not unique physical vehicles or the Indian market. A duplicate index row
cannot improve the numerator. Missing results identify work; do not repair the
sample by copying the app's inventory into the denominator.

The snapshot reuses canonical latest/sold/expiry/source-disable rules under
read-only repeatable read. Input is limited to 10,000 records/5 MB; snapshots above
50,000 eligible offers fail explicitly. Sampling validity and representativeness
still require review. Passing this tool does not close the full coverage gate.
