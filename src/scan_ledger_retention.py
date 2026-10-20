"""Conservative whole-generation audit retention; never inventory deletion.

Dry-run is the default. Caller-owned connections remain uncommitted on success;
the transaction/savepoint rolls back this operation on failure. Candidate locks
are skipped, so reports cannot establish the total number of locked rows.
"""
from contextlib import nullcontext
from uuid import UUID

from .source_registry_db import _connect


def _limit(value, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError('Invalid retention limit')
    return value


def _reference(metadata, generation_id):
    if not isinstance(metadata, dict):
        return 'malformed'
    if 'continuation' not in metadata:
        return None
    continuation = metadata['continuation']
    if not isinstance(continuation, dict):
        return 'malformed'
    scan = continuation.get('scan_generation')
    if not isinstance(scan, dict):
        return 'malformed'
    try:
        referenced = UUID(str(scan.get('generation_id')))
    except (ValueError, TypeError, AttributeError):
        return 'malformed'
    return 'referenced' if referenced == generation_id else None


def retain_scan_ledger(*, apply=False, retention_days=30, generation_limit=10,
                       batch_limit=100, membership_limit=1000, candidate_limit=50,
                       _connection=None):
    """Inspect a bounded candidate window under queue-before-generation locks.

    No schedules or environment switches activate this operation. Bounds include
    cascaded child rows. Oversized generations remain intact and are reported.
    """
    if type(apply) is not bool or type(retention_days) is not int or not 30 <= retention_days <= 3650:
        raise ValueError('Retention requires explicit boolean apply and at least 30 days')
    _limit(generation_limit,10)
    _limit(batch_limit,100)
    _limit(membership_limit,1000)
    _limit(candidate_limit,200)
    report = dict(apply=apply, retention_days=retention_days, inspected=0,
        eligible_generations=0,eligible_batches=0,eligible_memberships=0,
        deleted_generations=0,deleted_batches=0,deleted_memberships=0,
        skipped={key:0 for key in ('active','referenced','malformed','recent',
                                  'incomplete','oversized','unavailable','budget')},
        locked_counts_available=False)
    with (nullcontext(_connection) if _connection is not None else _connect()) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""with previous as materialized (
                    select current_setting('lock_timeout') as prior_lock,
                           current_setting('statement_timeout') as prior_statement)
                    select now()-make_interval(days=>%s) as cutoff,prior_lock,prior_statement,
                    set_config('lock_timeout','2s',true),
                    set_config('statement_timeout','10s',true) from previous""",(retention_days,))
                settings = cur.fetchone()
                cutoff = settings['cutoff']
                # This list is a hint only; all eligibility is rechecked under locks.
                cur.execute("""select generation_id,refresh_id from inventory_scan_generations
                    where captured_at<%s and coalesce(last_batch_at,captured_at)<%s
                    order by captured_at,generation_id limit %s""",(cutoff,cutoff,candidate_limit))
                candidates = cur.fetchall()
                for candidate in candidates:
                    if report['eligible_generations'] >= generation_limit:
                        report['skipped']['budget'] += 1
                        break
                    report['inspected'] += 1
                    cur.execute("""select status,metadata from inventory_refresh_queue
                        where refresh_id=%s for update skip locked""",(candidate['refresh_id'],))
                    queue = cur.fetchone()
                    if not queue:
                        report['skipped']['unavailable'] += 1
                        continue
                    if queue['status'] in ('queued','running'):
                        report['skipped']['active'] += 1
                        continue
                    reason = _reference(queue['metadata'],candidate['generation_id'])
                    if reason:
                        report['skipped'][reason] += 1
                        continue
                    cur.execute("""select captured_at,last_batch_at from inventory_scan_generations
                        where generation_id=%s and refresh_id=%s for update skip locked""",
                        (candidate['generation_id'],candidate['refresh_id']))
                    current = cur.fetchone()
                    if not current:
                        report['skipped']['unavailable'] += 1
                        continue
                    if current['captured_at'] >= cutoff or (current['last_batch_at'] or current['captured_at']) >= cutoff:
                        report['skipped']['recent'] += 1
                        continue
                    batch_remaining = batch_limit-report['eligible_batches']
                    member_remaining = membership_limit-report['eligible_memberships']
                    cur.execute("""select completed_at,claim_started_at from inventory_scan_batches
                        where generation_id=%s limit %s for update""",(candidate['generation_id'],batch_remaining+1))
                    batches = cur.fetchall()
                    if len(batches)>batch_remaining:
                        report['skipped']['oversized'] += 1
                        continue
                    if any(row['completed_at'] is None for row in batches):
                        report['skipped']['incomplete'] += 1
                        continue
                    if any(row['completed_at'] >= cutoff or row['claim_started_at'] >= cutoff for row in batches):
                        report['skipped']['recent'] += 1
                        continue
                    cur.execute("""select m.observation_id from inventory_scan_memberships m
                        join inventory_scan_batches b on b.batch_id=m.batch_id
                        where b.generation_id=%s limit %s""",(candidate['generation_id'],member_remaining+1))
                    members = cur.fetchall()
                    if len(members)>member_remaining:
                        report['skipped']['oversized'] += 1
                        continue
                    report['eligible_generations'] += 1
                    report['eligible_batches'] += len(batches)
                    report['eligible_memberships'] += len(members)
                    if apply:
                        cur.execute('delete from inventory_scan_generations where generation_id=%s returning generation_id',
                                    (candidate['generation_id'],))
                        if not cur.fetchone():
                            raise RuntimeError('Locked retention candidate disappeared')
                        report['deleted_generations'] += 1
                        report['deleted_batches'] += len(batches)
                        report['deleted_memberships'] += len(members)
                # Restore caller-owned transaction settings on success. On failure,
                # the enclosing transaction/savepoint restores them through rollback.
                cur.execute("select set_config('lock_timeout',%s,true),"
                            "set_config('statement_timeout',%s,true)",
                            (settings['prior_lock'],settings['prior_statement']))
    return report
