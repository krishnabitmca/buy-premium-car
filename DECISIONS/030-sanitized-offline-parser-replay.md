# ADR 030 — Bounded sanitized offline parser replay

Status: operator-only first slice; production capture and retention remain gated.

Reuse the reviewed Fusion card parser and catalogue tombstone extractor. Retain
rebuilt allowlisted cards rather than raw responses, scripts, cookies, bootstrap
material, images or buyer data. Cap input at 1 MiB, selected cards at five and the
complete serialized artifact at 64 KiB. Explicit statuses and selection limits
prevent a sample being mistaken for complete traversal.

Artifacts carry versions, source context, hashes, creation time, a local taxonomy
snapshot, an optional operator-provided generation UUID and normalized expected
results. The UUID is not verified ledger membership. Creation time is not stock
freshness. Hashes detect corruption; they do not authenticate authors.

Replay validates artifacts and sanitized HTML again, sets/resets the local brand
context and calls existing parsers without network or registry reads. Results are
historical diagnostics: matched, drift or replay unavailable. They cannot enter
ingestion, renew offers, retire omitted listings or prove physical availability.

Start with local operator commands and adversarial privacy checks. No worker
hook, HTTP route, database migration, credential or scheduled retention is added.
Automatic capture needs reviewed transaction linkage, storage/privacy bounds,
retention and operational evidence. P1-02 remains incomplete.
