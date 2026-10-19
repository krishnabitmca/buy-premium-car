"""Bounded operator verification against existing approved inventory infrastructure.

One queued acquisition, one page budget, no source activation or notifications.
Sustained ledger collection stays disabled outside this process.
"""
import argparse
import json
import os
from src.inventory_refresh_worker import claim_jobs, process_job
from src.source_registry_db import _connect, require_database


def verify(source_name, brand=None):
    require_database()
    if os.getenv('CARSCANNER_SCAN_LEDGER_ENABLED', '').lower() != 'true':
        raise ValueError('Controlled verification requires explicit ledger opt-in')
    if not isinstance(source_name,str) or not source_name.strip() or len(source_name)>200:
        raise ValueError('An existing verified source name is required')
    os.environ['CARSCANNER_MAX_PAGES_PER_SOURCE']='1'
    with _connect() as conn:
        source=conn.execute("""select s.source_id from sources s where s.name=%s
            and s.enabled and s.adapter_status='live' and exists(select 1 from
            source_adapters a where a.source_id=s.source_id and a.status='verified')""",
            (source_name,)).fetchone()
        if source is None:
            raise ValueError('Source is not enabled and verified')
        start=conn.execute('select clock_timestamp() as stamp,current_user as role').fetchone()
        for table in ('inventory_scan_generations','inventory_scan_batches','inventory_scan_memberships'):
            rights=conn.execute("""select has_table_privilege(current_user,%s,'SELECT')
                and has_table_privilege(current_user,%s,'INSERT')
                and has_table_privilege(current_user,%s,'UPDATE') as allowed""",
                ('public.'+table,)*3).fetchone()
            if not rights['allowed']:
                raise RuntimeError('Worker role lacks ledger access')
        conn.commit()
    jobs=claim_jobs(1,source_names=[source_name],brands=[brand] if brand else None)
    if len(jobs)!=1:
        raise RuntimeError('No claimable queued work for controlled verification')
    job=jobs[0]
    result=process_job(job)
    if result.get('deferred') or result.get('superseded'):
        raise RuntimeError('Controlled acquisition deferred or superseded')
    with _connect() as conn:
        batches=conn.execute("""select b.batch_id,b.accepted_count,g.completeness_verified,
            g.absence_reconciliation_permitted,count(m.observation_id) as memberships,
            count(m.observation_id) filter(where m.evidence_kind='positive') as positive_observations
            from inventory_scan_batches b join inventory_scan_generations g using(generation_id)
            left join inventory_scan_memberships m on m.batch_id=b.batch_id
            where b.source_id=%s and b.refresh_id=%s and b.attempt_count=%s
              and b.claim_started_at=%s and b.completed_at is not null
            group by b.batch_id,g.completeness_verified,g.absence_reconciliation_permitted""",
            (source['source_id'],job['refresh_id'],job['attempt_count'],job['started_at'])).fetchall()
    if len(batches)!=1:
        raise RuntimeError('Expected one committed ledger batch; work may be deferred or unavailable')
    batch=batches[0]
    if (batch['memberships']!=batch['accepted_count'] or batch['completeness_verified']
            or batch['absence_reconciliation_permitted']):
        raise RuntimeError('Ledger verification invariant failed')
    if not batch['positive_observations']:
        raise RuntimeError('Batch committed without accepted observations; positive membership unverified')
    return dict(ok=True,source=source_name,worker_role=start['role'],
        batch_id=str(batch['batch_id']),accepted_observations=batch['accepted_count'],
        memberships=batch['memberships'],positive_observations=batch['positive_observations'],
        completeness_verified=False,
        absence_reconciliation_permitted=False,maximum_jobs=1,page_budget=1)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True)
    parser.add_argument('--brand')
    args=parser.parse_args()
    print(json.dumps(verify(args.source,args.brand)))
