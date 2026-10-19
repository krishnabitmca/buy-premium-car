# ADR 029 — Private transactional scan-write ledger

Status: implemented behind an off-by-default gate; production migration and
activation require separately verified evidence. P1-02 remains incomplete.

Use the existing claim-fenced PostgreSQL transaction to persist generations,
stable claim batches and exact accepted observation memberships. Canonical
ingestion, explicit negatives, ledger and queue checkpoint commit or roll back
together. No network work is moved into transactions. Model-frontier expansion
currently precedes this fence and is not covered by its atomicity claim.

Membership uses observation/listing/source IDs from actual inserts. It is neither
parser-card membership nor physical-car verification. Repeated observations of
one listing remain distinct. Composite foreign keys reject cross-source writes.
Generation fingerprints/start/source/queue identity cannot silently change through
the helper. Duplicate committed claims are rejected before repeat ingestion.

The only generation states are partial and exhausted_unverified. Database checks
keep completeness_verified and absence_reconciliation_permitted false. No absent
listing is removed; latest evidence and existing expiry/sold rules remain intact.
Legacy continuations explicitly retain incomplete history; no synthetic backfill.

The CLI-generated additive migration enables RLS and revokes public/browser access.
There are no public routes, security-definer functions, new credentials or projection
revision triggers. Existing server-role access must be verified before activation.

CARSCANNER_SCAN_LEDGER_ENABLED defaults false. Apply and inspect migration first,
then verify a controlled worker transaction, security advisors and actual role
access before enabling any sustained collection. Existing workers remain compatible
with an unmigrated database while the gate is off. Disable the gate for rollback;
do not drop canonical inventory or ledger evidence to roll back application code.

Bounded evidence retention, sanitized parser replay, operational reporting and
sustained production collection remain subsequent gates. No national coverage,
freshness or scale conclusion follows from this audit ledger.
