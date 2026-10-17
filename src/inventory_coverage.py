"""Audit all supported makes against the same current-inventory projection as search.

Counts describe observations in our index, never total marketplace inventory.
Run outside customer requests; no crawler or model calls are made here.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .inventory_db import search_inventory
from .inventory_refresh_planner import baseline_brand_demands
from .source_registry_db import _connect, require_database


def coverage_report():
    require_database()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""select lower(q.brand) as brand,s.name as source,q.status,
            q.started_at,q.completed_at,q.last_error is not null as last_attempt_failed,
            q.metadata->>'last_success_at' as last_complete_scan,
            coalesce((q.metadata->>'pages_fetched')::integer,0) as pages_fetched,
            q.metadata ? 'continuation' as traversal_pending
            from inventory_refresh_queue q join sources s using(source_id)
            where q.brand<>'' and q.model='' and q.condition='both'
              and q.destination_state='' and s.enabled and s.adapter_status='live'
            order by lower(q.brand),s.name,q.started_at desc nulls last,q.refresh_id desc""")
        scans = {}
        # Historical case-variant queue keys may coexist. Report their latest
        # attempt rather than counting duplicate queue rows as extra coverage.
        for row in cur.fetchall():
            scans.setdefault((row['brand'],row['source']),dict(row))
        cur.execute("""select q.brand,q.model,s.name as source,q.status,
            q.started_at,q.completed_at,q.metadata->'model_discovery' as discovery_evidence,
            q.metadata->'advertised_model_count' as advertised_model_count,
            coalesce((q.metadata->>'pages_fetched')::integer,0) as pages_fetched,
            q.metadata ? 'continuation' as traversal_pending,
            q.last_error is not null as last_attempt_failed
            from inventory_refresh_queue q join sources s using(source_id)
            where q.metadata ? 'model_discovery' and s.enabled and s.adapter_status='live'
            order by q.brand,q.model,s.name""")
        model_scans=[dict(row) for row in cur.fetchall()]
    makes=[]
    for demand in baseline_brand_demands():
        brand=demand['brand']
        conditions={}
        for condition in ('used','demo'):
            _,_,total,summary=search_inventory(query=brand,condition=condition,
                limit=1,return_count=True,with_summary=True,require_persistence=True)
            conditions[condition]={
                'indexed_results':total,'sources':summary.get('sources',[]),
                'seller_location_labels':summary.get('cities',[]),
                'status':'partial_inventory' if total else 'coverage_gap',
            }
        makes.append({'brand':brand,'conditions':conditions,
            'scans':[row for (make,_),row in scans.items() if make==brand.lower()]})
    return {'generated_at':datetime.now(timezone.utc).isoformat(),
        'model_frontier':model_scans,
        'scope':'india','complete_market_coverage':False,
        'meaning':'Current eligible indexed results; zero is a coverage gap, not proof of no cars.',
        'brands':makes}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=coverage_report()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'brands_checked':len(report['brands']),
        'used_coverage_gaps':[b['brand'] for b in report['brands'] if not b['conditions']['used']['indexed_results']],
        'demo_coverage_gaps':[b['brand'] for b in report['brands'] if not b['conditions']['demo']['indexed_results']]}))


if __name__=='__main__':
    main()
