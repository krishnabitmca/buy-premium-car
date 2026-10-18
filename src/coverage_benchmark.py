"""Private sampled-source recall benchmark, never a national completeness claim."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from .inventory_db import eligibility_predicates
from .inventory_freshness import global_expiry_minutes
from .source_registry_db import _connect, require_database


def url_key(value):
    parsed=urlsplit(str(value))
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Sample URLs must be public HTTP(S) listing identifiers without credentials')
    query=[(k,v) for k,v in parse_qsl(parsed.query,keep_blank_values=True)
           if not k.lower().startswith('utm_') and k.lower() not in {'gclid','fbclid'}]
    return urlunsplit((parsed.scheme,parsed.netloc.lower(),parsed.path.rstrip('/') or '/',
                      urlencode(sorted(query)),''))


def text_key(value):return re.sub(r'[^a-z0-9]+','',str(value).casefold())


def validate_sample(document,now):
    if not isinstance(document,dict):raise ValueError('Sample must be an object')
    if document.get('version')!=1:raise ValueError('Sample version must be 1')
    sampling=document.get('sampling') or {}
    if not isinstance(sampling,dict):raise ValueError('Sampling provenance must be an object')
    if sampling.get('method')!='manual_source_review':
        raise ValueError('An independently collected manual source review is required; inventory exports are not benchmarks')
    if not sampling.get('reviewer') or not sampling.get('scope'):
        raise ValueError('Declare a reviewer identifier and sampling scope')
    try:collected=datetime.fromisoformat(str(sampling['collected_at']).replace('Z','+00:00'))
    except (ValueError,KeyError):raise ValueError('Declare a timezone-aware collected_at') from None
    if collected.tzinfo is None or not now-timedelta(hours=24)<=collected<=now:
        raise ValueError('Sample must be timezone-aware, no more than 24 hours old and not future-dated')
    records=document.get('records')
    if not isinstance(records,list) or not 1<=len(records)<=10000:
        raise ValueError('Provide 1–10000 manually labelled source listings')
    seen=set()
    for record in records:
        if not isinstance(record,dict):raise ValueError('Every source listing must be an object')
        if type(record.get('eligible')) is not bool:raise ValueError('Every listing needs an explicit boolean eligibility label')
        for field in ('source','brand','model','seller_state'):
            if not isinstance(record.get(field),str) or not 1<=len(record[field].strip())<=200:
                raise ValueError('Every listing needs source, brand, model and seller_state labels')
        if record.get('condition') not in {'used','demo'}:raise ValueError('Condition must be source-labelled used or demo')
        key=(record['source'].strip().casefold(),url_key(record.get('url','')))
        if key in seen:raise ValueError('Duplicate sampled source listing; tracking variants cannot inflate the denominator')
        seen.add(key)
    return records


def evaluate_sample(document,offers,*,now=None):
    now=now or datetime.now(timezone.utc)
    records=validate_sample(document,now)
    lookup=defaultdict(list)
    for offer in offers:
        for url in {offer.get('url'),offer.get('final_url')} - {None,''}:
            lookup[(str(offer['source']).strip().casefold(),url_key(url))].append(offer)
    results=[];ineligible_indexed=[];buckets=defaultdict(lambda:{'eligible_sample':0,'matched':0})
    for record in records:
        candidates=lookup.get((record['source'].strip().casefold(),url_key(record['url'])),[])
        if not record['eligible']:
            if candidates:ineligible_indexed.append({**record,'status':'unexpectedly_eligible'})
            continue
        matched=any(all(text_key(item.get(field,''))==text_key(record[field])
                        for field in ('brand','model','condition')) for item in candidates)
        results.append({**record,'status':'matched' if matched else 'attribute_mismatch' if candidates else 'missing'})
        for dimension in ('source','brand','model','seller_state','condition'):
            bucket=buckets[(dimension,record[dimension])]
            bucket['eligible_sample']+=1;bucket['matched']+=int(matched)
    total=len(results);matched=sum(row['status']=='matched' for row in results)
    return {'scope':document['sampling'],'evaluated_at':now.isoformat(),
            'measurement':'recall_within_declared_manual_sample','independence':'collector_attested_not_machine_verified',
            'national_coverage_established':False,'sample_size':len(records),'eligible_sample':total,
            'excluded_sample':len(records)-total,'matched':matched,'sample_recall':matched/total if total else None,
            'ineligible_indexed_count':len(ineligible_indexed),'ineligible_indexed':ineligible_indexed,
            'strata':[{'dimension':dim,'value':value,**counts,
                       'sample_recall':counts['matched']/counts['eligible_sample']}
                      for (dim,value),counts in sorted(buckets.items())],
            'gaps':[row for row in results if row['status']!='matched']}


def benchmark_database(document):
    require_database()
    # Validate before spending database capacity; snapshot time is captured below.
    validate_sample(document,datetime.now(timezone.utc))
    predicates=' and '.join(eligibility_predicates())
    with _connect() as conn,conn.cursor() as cur:
        cur.execute('set transaction isolation level repeatable read, read only')
        cur.execute("set local statement_timeout='10000ms'")
        cur.execute('select now() as snapshot_at')
        snapshot_at=cur.fetchone()['snapshot_at']
        cur.execute("""select s.name as source,l.url,l.final_url,v.brand,v.model,v.condition
            from public.listings l join lateral (
                select observation.* from public.vehicle_observations observation
                where observation.listing_id=l.listing_id
                order by observation.observed_at desc,observation.observation_id desc limit 1
            ) o on true
            join public.vehicles v on v.vehicle_id=l.vehicle_id and v.vehicle_id=o.vehicle_id
            join public.sources s on s.source_id=o.source_id
            where """+predicates+" order by l.listing_id limit 50001",
            (global_expiry_minutes(),global_expiry_minutes()))
        offers=cur.fetchall()
    if len(offers)>50000:raise ValueError('Benchmark snapshot exceeds 50000 offers; no incomplete score emitted')
    result=evaluate_sample(document,offers,now=snapshot_at)
    result['snapshot_eligible_offers']=len(offers)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.sample.stat().st_size>5_000_000:raise ValueError('Sample exceeds 5 MB')
    result=benchmark_database(json.loads(args.sample.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:result[key] for key in ('eligible_sample','matched','sample_recall','national_coverage_established')}))


if __name__=='__main__':main()
