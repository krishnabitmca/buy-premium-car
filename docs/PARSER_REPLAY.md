# Sanitized parser samples and offline replay

The first operator-only strategy is Fusion public catalogue cards. It tests the
existing parse_reviewed_cards and catalogue_tombstones functions. It does not
reacquire or ingest inventory. Input is a locally saved public source HTML file;
keep originals outside version control and exclude private/account documents.

Limits: 1 MiB input, five selected cards, 64 KiB complete artifact. Unsupported,
oversized or unusable input gets an explicit status. Free-text/contact and unsafe
link guards are conservative. No raw response is saved by these commands.
Sanitizable cards with no positive or explicit-negative parser evidence remain
`no_supported_cards`, rather than yielding a vacuous successful replay. Samples
are diagnostic evidence only; an empty/challenge response cannot retire inventory.

Example using the public synthetic fixture, which is not live stock:

    python -m scripts.parser_replay capture --input tests/fixtures/reviewed_fusion.html --output sample.json --source-url https://fusioncars.in/brand/mercedes-benz/
    python -m scripts.parser_replay replay --input sample.json

Capture refuses to overwrite existing output; replay is read-only. Both print
bounded JSON diagnostics and return exit 2 for failed/unavailable/drift outcomes.
Neither needs a database credential or network fetch. A match establishes parser
agreement on this historical sample, not coverage, freshness or availability.

The optional --generation UUID is an operator reference, not verified association
with a persisted scan. Timestamps describe sample creation. Hash checks detect
corruption rather than signed provenance. No automatic store, retention job,
worker capture hook or production ingestion path is enabled. See ADR 030.
