# P1-02 accepted-observation prerequisite

The optional private `_accepted_observations` list in `ingest_vehicles` and
`retire_catalogue_evidence` captures immutable source/listing/inserted-observation
identities for later scan membership. Existing callers receive unchanged counters.
PR 74 wires collection and a private ledger behind an off-by-default worker gate.
See SCAN_LEDGER.md. The controlled live check currently fails its server-role
access preflight; no live ledger operation or sustained collection is verified.

Records use actual `INSERT ... RETURNING observation_id`, not parser rows, latest
observation lookup, URL re-resolution or canonical vehicle identity. Rejected rows
produce no record; repeated observations of one listing remain distinct. Positive
means an accepted write, not eligibility or proof of current physical availability.
The records contain IDs/evidence kind only, with no listing/buyer payload.

Functions stage records locally and publish to the collector only after successful
completion, including commit/context exit when ingestion owns its connection.
For supplied connections, records remain provisional until the caller commits;
the caller must scope and discard them after rollback. Do not emit events, write
external files, or otherwise publish provisional IDs. Keep the collector inside
the existing fenced transaction when wiring the ledger.

## Implemented ledger and remaining work

Private generation/batch/observation tables now exist through a CLI-generated
additive migration with RLS and no browser grants. The gated worker writes batch
membership and canonical observations/checkpoint in the same claim transaction. It enforces
source and immutable generation consistency, stable batch identity, replay safety
and distinct observations. It preserves partial legacy history and deny completeness/
absence authority. No network work inside the transaction. Model-frontier enqueue
currently sits outside this boundary; do not include it in atomicity claims.

Follow with bounded sanitized offline parser samples for one reviewed strategy,
with explicit unsupported/truncated/replay-unavailable states and retention.
Do not retain raw bootstrap/session material or re-ingest fixtures as live stock.
The broader LLD and adversarial matrix are in the workspace's
outputs/P1_02_SCAN_LEDGER_LLD_2026-10-19.md. P1-02 remains incomplete.
