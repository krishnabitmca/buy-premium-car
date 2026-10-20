# Controlled parser evidence capture

Implementation is gated, not yet an operational acceptance result. See ADR031.
Ordinary customer search and scheduled collection do not capture samples.

The main-only Controlled Scan Ledger Verification workflow has an optional
`capture_sample` input, false by default. It supports only an existing enabled,
verified Fusion source and one queued job/page budget. It uses the existing worker
credential without expanding its privileges or enabling continuous collection.
Do not dispatch against unreviewed sources or synthesize a replacement job if no
eligible queued work exists.

The private capture buffer uses the already fetched page: no added HTTP requests.
At most two attempts, five cards per sample, 1 MiB input, 64 KiB per artifact and
128 KiB aggregate staged samples. Invalid/challenge/oversized pages are missing
evidence, never stock absence. Capture time is not verified stock freshness.

The verifier first checks the exact committed ledger claim and membership counts.
Only then does it export fixed sample files and a receipt into a new exclusive
directory. The receipt records source, generation, batch and claim identities,
completion time, counts, outcomes and file hashes. It does not assert that sampled
cards explain every accepted member, that source enumeration is complete, or that
files and DB writes form one atomic transaction. Hashes are integrity checks,
not signatures or proof of current vehicle availability.

Capture/export failure remains separate from committed ingestion. A missing or
failed export yields a nonzero verification result without retrying acquisition,
rewriting canonical inventory or marking the committed queue job failed. A crash
before receipt completion leaves an incomplete artifact set. Never call partial
files a verified export. Upload failure means remote persistence is unverified.

The workflow uploads only fixed sanitized JSON samples, receipt and bounded
verification status, retained seven days. Full source HTML, secrets, hidden files
and arbitrary workspace directories are excluded. Assume repository artifact
readers can inspect the contents; do not use uploads as a private secret store.

Operational gate still open: real controlled acquisition → exact committed batch
receipt → bounded upload → downloaded-file hash check → offline replay, with
private data checks and existing false completeness/absence flags throughout.
This demonstration must be verified independently from green fixture tests.
