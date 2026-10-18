# 022: Full identifier evidence and private legacy review

Partial/placeholder chassis strings previously acquired a `vin:` key at eight
characters and confidence 1.0. That could turn weak evidence into an exact
cross-source physical-car grouping. Parser-provided confidence could also override
the canonical provisional confidence during ingestion.

Only a complete 17-character modern VIN-form identifier can supply an exact
cross-source key. Accept case/outer whitespace normalization, exclude I/O/Q,
punctuation, masks, all-digit/all-letter and obvious repeated placeholders. Never
strip arbitrary characters into a plausible VIN. A full chassis field meeting
the same format can be used, with its field provenance retained. Unsupported
historical/local chassis formats remain source-offer-scoped provisional records.

This is a conservative matching policy, not an India registration/legal rule or
manufacturer validation. The 17-character/I-O-Q reference is the NHTSA manufacturer
handbook: https://vpic.nhtsa.dot.gov/documents/ManufacturerHandbook.pdf
Do not impose its US check-digit requirements on all Indian/imported vehicles.
Format matching cannot prove physical identity, ownership or an authentic VIN.
The existing exact-key numeric confidence is not a calibrated probability.

Two different full identifiers in one incoming record produce conflict evidence,
not a field-order winner. Partial/invalid/conflicting identifiers cannot indirectly
get a shared attribute-bucket candidate key. Ingestion derives confidence from
canonical evidence rather than accepting the parser's generic confidence floor.
Existing identifier-absent candidate proposals retain their current behavior;
their quality and same-VIN attribute contradictions still need labelled validation
and reviewed conflict/merge/split tooling. This does not close A12/SE06 wholesale.

Private `python -m src.identity_audit --output <path>` reports invalid/legacy
confirmed keys under a read-only transaction and bounded statement timeout. It
hashes identity keys in output, reports truncation, and never changes inventory.
No public endpoint, new credentials, schema or automatic repair is introduced.
Do not infer that every legacy confirmation is false; it requires review.

The initial read-only production aggregate found 6,967 vehicles and zero confirmed
vehicles/invalid confirmed keys. This is a dated snapshot, not a matching-quality
benchmark. No production data was rewritten by the audit.
