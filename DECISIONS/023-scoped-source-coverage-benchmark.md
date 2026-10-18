# 023: Measure sampled source recall against canonical eligible offers

Registered brands, source counts and raw listing totals are not a national
coverage denominator. Add a private benchmark CLI accepting an independently
collected, explicitly labelled source sample, rather than manufacturing coverage
percentages from the same crawler output being evaluated.

`python -m src.coverage_benchmark --sample <json> --output <json>` validates version,
collection method/reviewer/scope/time and per-listing labels. Reject inventory
exports as collection provenance, samples older than 24 hours, future/naive dates,
duplicate source URLs and missing eligibility labels. Collector independence is
attested metadata, not something the program can establish automatically.

Read source offers using the same latest-observation join and eligibility
predicates as buyer search, in one read-only repeatable-read snapshot. Keep sold,
expired, disabled-source and non-live-adapter offers out. Apply a ten-second SQL
statement budget and refuse more than 50,000 eligible offers rather than scoring
a silently truncated dataset. No schema, source activation or public route changes.

Match source plus listing URL, preserving query parameters that identify stock;
strip fragments and known tracking parameters only. Require matching normalized
brand/model/condition labels for usable recall. Different sources or different
stock query IDs cannot count as the same sample listing. Sample model labels must
follow the documented canonical representation, including trim where stored;
attribute mismatches are separate diagnostics rather than invisible URL matches.

Report numerator/denominator, gaps and source/brand/model/state/condition strata.
Explicitly ineligible labels do not inflate the recall denominator; report any
that are nevertheless eligible in the current index as unexpected inclusions.
With no eligible sample, emit null recall. Never label this national completeness.

Human-reviewed, representative multi-source used/demo sampling and real identity
labels remain release gates. An agent-inspected UI smoke sample can validate the
workflow, but is not a human gold dataset or a representative market benchmark.
The 24-hour limit reduces temporal drift; it cannot prove physical availability.
