"""Private read-only legacy identity audit; never merges/splits inventory."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from .canonical_identity import normalized_full_vin
from .source_registry_db import _connect, require_database


def assess_record(row):
    key=str(row.get('identity_key') or '')
    reasons=[]
    if key.startswith('vin:') and normalized_full_vin(key[4:]) is None:
        reasons.append('legacy_invalid_full_vin')
    evidence=row.get('identity_evidence') or {}
    if row.get('identity_state')=='confirmed' and evidence.get('identity_policy')!='full-vin-v1':
        reasons.append('legacy_confirmation_requires_review')
    if not reasons:return None
    return {'vehicle_id':str(row['vehicle_id']),
            'identity_key_hash':hashlib.sha256(key.encode()).hexdigest(),
            'reasons':reasons,'listing_count':int(row.get('listing_count') or 0),
            'source_count':int(row.get('source_count') or 0)}


def audit_identities(limit=10000):
    require_database()
    if not 1<=limit<=100000:raise ValueError('limit must be between 1 and 100000')
    with _connect() as conn,conn.cursor() as cur:
        cur.execute('set transaction read only')
        cur.execute("set local statement_timeout='10000ms'")
        cur.execute("""select v.vehicle_id,v.identity_key,v.identity_state,v.identity_evidence,
            count(l.listing_id) as listing_count,count(distinct l.source_id) as source_count
            from vehicles v left join listings l using(vehicle_id)
            where v.identity_state='confirmed' or v.identity_key like 'vin:%%'
            group by v.vehicle_id order by v.vehicle_id limit %s""",(limit+1,))
        records=cur.fetchall()
    checked=records[:limit]
    findings=[finding for row in checked if (finding:=assess_record(row))]
    return {'read_only':True,'policy':'full-vin-v1','checked':len(checked),
            'truncated':len(records)>limit,'review_required':len(findings),
            'invalid_full_vin':sum('legacy_invalid_full_vin' in x['reasons'] for x in findings),
            'findings':findings}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=10000)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=audit_identities(args.limit)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='findings'}))


if __name__=='__main__':main()
