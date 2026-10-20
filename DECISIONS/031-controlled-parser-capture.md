# ADR 031 — Controlled post-commit parser evidence capture

Status: implementation in progress; disabled by default, not operationally verified.

Extend ADR030's operator-only replay with one explicit manual Fusion acquisition.
The verifier requires both its capture-directory option and process opt-in before
claiming work. Background adapter capture reuses fetched HTML and the actual scan
generation; web search and ordinary scheduled workers receive no capture buffer.

Hold at most two attempts of bounded sanitized evidence in memory. Never persist
raw HTTP responses, credentials, arbitrary page fields or capture errors. Existing
source fetch budgets, parser behavior, ingestion and sold-evidence rules remain.

Only after process_job commits does the verifier read the exact source/refresh/
attempt/claim timestamp tuple. Export associates samples with that batch and
generation in a separate receipt; source/generation mismatch fails closed. It is
not a transactional blob store, signed provenance or coverage proof. A crash
between commit and export leaves missing diagnostic evidence, not failed inventory.
File-export failures must never enter worker retry/failure bookkeeping.

Use exclusive new bounded directories, fixed file names, compact JSON, sample/file
hashes and receipt-last writing. Existing GitHub artifact upload retains selected
sanitized files for seven days. No new DB tables, privileges or storage service.
Repository artifact access may include authenticated repository readers; samples
must be safe for that audience. No claim that the artifacts are private secrets.

The manual workflow's capture input defaults false. Global capture and continuous
ledger collection remain off. Activation requires independent privacy review,
regression/CI and one controlled real-source capture/export/replay demonstration.
This does not close sustained operation, restore, retention or P1-02 acceptance.
