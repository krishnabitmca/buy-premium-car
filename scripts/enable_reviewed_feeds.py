"""Explicit rollout of the two reviewed adapters, after deploying their code."""
import argparse
import json
from pathlib import Path
import yaml
from src.source_adapters import AdapterRequest,BuiltinMarketplaceAdapter
from src.source_registry_db import require_database,sync_registry,_connect,source_key
from src.reviewed_inventory import reviewed_detail_evidence
from src.listing_evidence import fetch_listing

REVIEWED={'Skoda Certified Pre-Owned','Fusion Cars'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',action='append',required=True,choices=sorted(REVIEWED))
    parser.add_argument('--apply',action='store_true',help='Enable only after real stock and detail verification pass')
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
    sources=yaml.safe_load(Path('config/sources.yaml').read_text(encoding='utf-8'))['known_sources']
    selected=[s for s in sources if s['name'] in args.source]
    results=[]
    for source in selected:
        result=BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(continuation={}))
        if result.status!='live' or len(result.listings)<2:raise RuntimeError(source['name']+': stock verification failed')
        row=result.listings[0]
        evidence=reviewed_detail_evidence(fetch_listing(row['url']),row['url'],row['brand'],row['model'])
        if evidence.get('outcome')!='available' or evidence.get('price_lakh')!=row['price_lakh']:
            raise RuntimeError(source['name']+': individual detail verification failed')
        results.append(dict(source=source['name'],listings=len(result.listings),pages=result.pages_fetched,
            detail_url=row['url'],detail_evidence=evidence,continuation_pending=bool(result.continuation)))
    # Run all HTTP verification before any registry mutation. Discovery cannot
    # invoke this explicit reviewed-adapter rollout path.
    if args.apply:
        require_database();sync_registry(selected)
        with _connect() as conn,conn.cursor() as cur:
            for source in selected:
                key=source_key(source)
                cur.execute('select source_id from sources where source_key=%s',(key,));sid=cur.fetchone()['source_id']
                if source['name']=='Skoda Certified Pre-Owned':
                    cur.execute("update source_endpoints set is_active=false where source_id=%s and url='https://www.skodapreowned.in/'",(sid,))
                cur.execute("delete from source_capabilities where source_id=%s and capability_type='condition' and capability_value<>'used'",(sid,))
                cur.execute("""insert into source_adapters(source_id,adapter_key,status,adapter_type,parser_version,
                    pagination_strategy,supports_brand,supports_model,supports_condition,last_verified_at,metadata)
                    values(%s,%s,'verified','builtin','reviewed-stock-v1',%s,true,true,true,now(),%s::jsonb)
                    on conflict(adapter_key) do update set status='verified',last_verified_at=now(),
                    parser_version=excluded.parser_version,metadata=excluded.metadata""",
                    (sid,key+'_reviewed_stock_v1','public_stock_api' if 'Skoda' in source['name'] else 'advertised_brand_catalogues',
                     json.dumps({'review':'individual priced stock and detail verified','parser_strategy':source['parser_strategy']})))
            conn.commit()
    report=dict(applied=args.apply,results=results)
    path=Path(args.report);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
