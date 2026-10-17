"""Restore reviewed parser settings without changing source lifecycle/access."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import yaml
from .source_registry_db import _connect, require_database, source_key

RUNTIME_KEYS = {
    'city_catalog_path_pattern','city_catalog_title_pattern','catalogue_link_pattern',
    'brand_slug_overrides',
    'parser_strategy', 'query_url_template', 'brand_query_url_template',
    'used_query_url_template', 'demo_query_url_template',
    'brand_used_query_url_template', 'brand_demo_query_url_template',
    'catalog_url', 'catalog_brand_url_template', 'catalog_exclude_paths',
}

def restore_config(sources, *, apply=False):
    require_database()
    changes=[]
    with _connect() as conn, conn.cursor() as cur:
        for source in sources:
            settings={k:v for k,v in source.items() if k in RUNTIME_KEYS}
            endpoints=source.get('endpoints') or []
            if not settings and not endpoints:
                continue
            cur.execute('select source_id,metadata from public.sources where source_key=%s',
                        (source_key(source),))
            row=cur.fetchone()
            if not row:
                continue
            metadata=row.get('metadata') or {}
            missing={k:v for k,v in settings.items() if k not in metadata}
            if missing:
                changes.append({'source':source['name'],'keys':sorted(missing)})
            if apply and missing:
                cur.execute('update public.sources set metadata=%s::jsonb || metadata where source_id=%s',
                            (json.dumps(missing),row['source_id']))
            for endpoint in endpoints:
                url=endpoint.get('url')
                if not url:
                    continue
                cur.execute('select 1 from public.source_endpoints where source_id=%s and url=%s',
                            (row['source_id'],url))
                if cur.fetchone():
                    continue
                changes.append({'source':source['name'],'endpoint':url})
                if apply:
                    cur.execute("""insert into public.source_endpoints
                        (source_id,url,endpoint_type,is_active,metadata)
                        values (%s,%s,'catalogue',true,%s::jsonb) on conflict do nothing""",
                        (row['source_id'],url,json.dumps({k:v for k,v in endpoint.items() if k!='url'})))
        if apply:
            conn.commit()
    return changes

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--source',action='append')
    group.add_argument('--all-existing',action='store_true')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    path=Path(__file__).resolve().parents[1]/'config/sources.yaml'
    sources=yaml.safe_load(path.read_text(encoding='utf-8'))['known_sources']
    selected=sources if args.all_existing else [s for s in sources if s['name'] in args.source]
    if not args.all_existing and set(args.source)-{s['name'] for s in selected}:
        parser.error('unknown source name')
    print(json.dumps(restore_config(selected,apply=args.apply)))

if __name__=='__main__':
    main()
