"""Private scan-write ledger. Caller owns the fenced transaction and commit.

These records describe accepted writes, never source completeness or eligibility.
An exception requires rolling back the enclosing transaction.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from uuid import UUID, NAMESPACE_URL, uuid5

from .scan_contract import CONTRACT_VERSION


def _uuid(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Invalid ledger UUID') from None


def _timestamp(value):
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Invalid ledger timestamp') from None


def _integer(value, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError('Invalid ledger count')
    return value


def _evidence(evidence, source_id):
    if not isinstance(evidence, dict):
        raise ValueError('Invalid scan evidence')
    if (type(evidence.get('contract_version')) is not int
            or evidence['contract_version'] != CONTRACT_VERSION
            or evidence.get('background_scan') is not True
            or evidence.get('completeness_verified') is not False
            or evidence.get('absence_reconciliation_permitted') is not False
            or evidence.get('execution_state') != 'batch_succeeded'
            or type(evidence.get('resumed_legacy_checkpoint')) is not bool):
        raise ValueError('Unsupported scan evidence contract')
    scope = evidence.get('scope')
    fingerprint = evidence.get('scope_fingerprint')
    if not isinstance(scope, dict) or _uuid(scope.get('source')) != source_id:
        raise ValueError('Scan scope source mismatch')
    if not isinstance(fingerprint, str) or not re.fullmatch('[0-9a-f]{64}', fingerprint):
        raise ValueError('Invalid scope fingerprint')
    try:
        encoded = json.dumps(scope, sort_keys=True, separators=(',', ':'), default=str).encode()
    except (ValueError, TypeError):
        raise ValueError('Invalid scan scope') from None
    if len(encoded) > 65536 or sha256(encoded).hexdigest() != fingerprint:
        raise ValueError('Scan scope fingerprint mismatch')
    terminal = evidence.get('terminal_reason')
    state = {'pending_pages': 'partial_traversal', 'frontier_exhausted': 'traversal_exhausted_unverified'}.get(terminal)
    if state is None or evidence.get('coverage_state') != state:
        raise ValueError('Invalid scan terminal state')
    _integer(evidence.get('pages_this_batch'))
    return dict(generation_id=_uuid(evidence.get('generation_id')), source_id=source_id,
                scope_fingerprint=fingerprint, started_at=_timestamp(evidence.get('started_at')),
                contract_version=CONTRACT_VERSION,
                legacy_partial_history=evidence['resumed_legacy_checkpoint'])


def prepare_batch(job, source_id, evidence, conn):
    """Reserve a batch AFTER the worker locks/checks its current queue claim.

    A committed duplicate is returned before ingestion. An incomplete duplicate
    is an invariant error, not permission to ingest again.
    """
    source_id = _uuid(source_id)
    generation = _evidence(evidence, source_id)
    refresh_id = _integer(job.get('refresh_id'), positive=True)
    attempt = _integer(job.get('attempt_count'), positive=True)
    started = _timestamp(job.get('started_at'))
    if _uuid(job.get('source_id')) != source_id:
        raise ValueError('Queue source mismatch')
    batch_id = uuid5(NAMESPACE_URL, f'carscanner:scan-batch:v1:{refresh_id}:{attempt}:{started.isoformat()}')
    with conn.cursor() as cur:
        cur.execute("""insert into inventory_scan_generations
            (generation_id,source_id,refresh_id,scope_fingerprint,started_at,contract_version,
             state,legacy_partial_history,completeness_verified,absence_reconciliation_permitted)
            values(%s,%s,%s,%s,%s,%s,'partial',%s,false,false)
            on conflict(generation_id) do nothing""",
            (generation['generation_id'],source_id,refresh_id,generation['scope_fingerprint'],
             generation['started_at'],CONTRACT_VERSION,generation['legacy_partial_history']))
        cur.execute('select * from inventory_scan_generations where generation_id=%s for update',
                    (generation['generation_id'],))
        existing = cur.fetchone()
        expected = {**generation, 'refresh_id': refresh_id}
        if not existing or any(existing.get(key) != value for key, value in expected.items()):
            raise ValueError('Generation immutable fields conflict')
        cur.execute("""insert into inventory_scan_batches
            (batch_id,generation_id,source_id,refresh_id,attempt_count,claim_started_at,
             pages_fetched,accepted_count,terminal_reason)
            values(%s,%s,%s,%s,%s,%s,0,0,'pending_pages')
            on conflict(batch_id) do nothing returning batch_id""",
            (batch_id,generation['generation_id'],source_id,refresh_id,attempt,started))
        inserted = cur.fetchone()
        if not inserted:
            cur.execute('select * from inventory_scan_batches where batch_id=%s for update', (batch_id,))
            previous = cur.fetchone()
            immutable = dict(generation_id=generation['generation_id'], source_id=source_id,
                             refresh_id=refresh_id, attempt_count=attempt, claim_started_at=started)
            if (not previous or any(previous.get(k) != v for k,v in immutable.items())
                    or previous.get('completed_at') is None):
                raise ValueError('Duplicate batch is conflicting or incomplete')
    return {**generation, 'refresh_id':refresh_id, 'batch_id':batch_id,
            'already_committed':not bool(inserted)}


def finish_batch(batch, accepted, evidence, continuation, conn):
    """Publish membership/checkpoint evidence inside the caller transaction."""
    if batch.get('already_committed'):
        raise ValueError('Cannot finish an already committed batch')
    checked = _evidence(evidence, batch['source_id'])
    if any(batch.get(key) != value for key,value in checked.items()):
        raise ValueError('Batch evidence changed')
    pending = evidence['terminal_reason'] == 'pending_pages'
    if pending:
        if not isinstance(continuation, dict) or not continuation:
            raise ValueError('Pending batch requires checkpoint')
        checkpoint = continuation.get('scan_generation')
        if (not isinstance(checkpoint, dict)
                or any(checkpoint.get(k) != evidence.get(k) for k in (
                    'generation_id','scope_fingerprint','contract_version','started_at','resumed_legacy_checkpoint'))):
            raise ValueError('Continuation generation mismatch')
    elif continuation is not None:
        raise ValueError('Exhausted batch cannot have a checkpoint')
    rows = []
    seen = set()
    for item in accepted:
        source_id = _uuid(item.source_id)
        observation_id = _integer(item.observation_id, positive=True)
        if source_id != batch['source_id'] or item.evidence_kind not in ('positive','explicit_negative'):
            raise ValueError('Accepted observation source/kind mismatch')
        if observation_id in seen:
            raise ValueError('Duplicate accepted observation')
        seen.add(observation_id)
        rows.append((batch['batch_id'],source_id,_uuid(item.listing_id),observation_id,item.evidence_kind))
    with conn.cursor() as cur:
        for row in rows:
            cur.execute("""insert into inventory_scan_memberships
                (batch_id,source_id,listing_id,observation_id,evidence_kind) values(%s,%s,%s,%s,%s)""", row)
        cur.execute("""update inventory_scan_batches set pages_fetched=%s,accepted_count=%s,
            terminal_reason=%s,completed_at=now() where batch_id=%s and completed_at is null
            returning batch_id""", (evidence['pages_this_batch'],len(rows),evidence['terminal_reason'],batch['batch_id']))
        if not cur.fetchone():
            raise ValueError('Batch was already finished or missing')
        cur.execute("""update inventory_scan_generations set last_batch_at=now(),
            state=case when state='exhausted_unverified' or %s then 'exhausted_unverified' else 'partial' end
            where generation_id=%s""", (not pending,batch['generation_id']))
