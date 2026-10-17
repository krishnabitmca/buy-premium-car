"""Source-evidenced used model discovery and durable acquisition fan-out."""
from __future__ import annotations
import json
import re
from datetime import datetime,timezone
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from . import live_marketplaces as lm
from .source_registry_db import _connect


def discover_models(html,source,base_url,query,rows):
    brand,_=lm._query_parts(query)
    if not brand:
        return []
    strategy=source.get('parser_strategy') or (source.get('metadata') or {}).get('parser_strategy')
    found={}
    if strategy in {'cardekho_cards','cartrade_cards'}:
        # This adapter's card heading is the observed model family; its separate
        # title carries the variant. Do not use CarWale variant strings as models.
        for row in rows:
            model=str(row.get('model') or '').strip()
            if model and lm._identity_matches_query(row,brand):
                found[model.lower()]={'model':model,'evidence_url':row['url'],
                    'discovery_kind':'observed_model'}
    if strategy=='carwale_cards':
        slug=lm._slug(lm._canonical_brand(brand))
        slug=(source.get('brand_slug_overrides') or (source.get('metadata') or {}).get('brand_slug_overrides') or {}).get(lm._canonical_brand(brand),slug)
        for anchor in BeautifulSoup(html,'html.parser').select('a[href]'):
            url=urljoin(base_url,anchor['href']);parts=urlsplit(url)
            if parts.hostname!=urlsplit(base_url).hostname or parts.query:
                continue
            match=re.fullmatch(r'/used/'+re.escape(slug)+r'-([a-z0-9-]+)/?',parts.path)
            if not match:
                continue
            if match[1] in {'cars','suv','sedan','hatchback','automatic','manual','diesel','petrol','electric','cng'}:
                continue
            model=match[1].replace('-',' ')
            label=anchor.get_text(' ',strip=True)
            count=re.match(r'^([\d,]+)\s+Used\b',label,re.I)
            if not count and not (lm._model_identity_matches(brand,label) and lm._model_identity_matches(model,label)):
                continue
            found[model]={'model':model,'evidence_url':url,'discovery_kind':'used_catalog_link',
                'advertised_count':int(count[1].replace(',','')) if count else None}
    return list(found.values())[:100]


def enqueue_models(brand,models):
    """Cross-source model scans only on reviewed, verified model-route adapters.

    Queue metadata is discovery evidence, never inventory or availability proof.
    Existing running/partial/failed work retains its status and checkpoint.
    """
    if not brand or not models:
        return 0
    # Stored display names may be aliases (MG Motor, Citroën). Use the search
    # make token so the worker never treats an alias suffix as part of a model.
    brand=lm._query_parts(brand)[0] or brand
    count=0
    with _connect() as conn,conn.cursor() as cur:
        for item in models:
            model=' '.join(str(item.get('model') or '').split()).lower()
            if not model or len(model)>100 or item.get('discovery_kind') not in {'observed_model','used_catalog_link'}:
                continue
            evidence={'model_discovery':item}
            if item.get('advertised_count') is not None:
                evidence['advertised_model_count']={'count':item['advertised_count'],
                    'evidence_url':item['evidence_url'],'observed_at':datetime.now(timezone.utc).isoformat(),
                    'meaning':'source-advertised used count; not verified indexed stock'}
            cur.execute("""insert into inventory_refresh_queue
                (source_id,brand,model,condition,destination_state,priority,reason,metadata)
                select s.source_id,%s,%s,'both','',20,'used_model_discovery',%s::jsonb
                from sources s where s.enabled and s.adapter_status='live'
                  and s.metadata->>'parser_strategy' in ('cardekho_cards','carwale_cards','cartrade_cards')
                  and s.metadata ? 'query_url_template'
                  and exists(select 1 from source_adapters a where a.source_id=s.source_id and a.status='verified')
                  and exists(select 1 from source_capabilities c where c.source_id=s.source_id
                    and c.capability_type='brand' and lower(c.capability_value) in (lower(%s),'all'))
                on conflict(source_id,brand,model,condition,destination_state)
                do update set metadata=inventory_refresh_queue.metadata || excluded.metadata""",
                (brand.strip().lower(),model,json.dumps(evidence),brand))
            count+=cur.rowcount
        conn.commit()
    return count


def reschedule_models():
    with _connect() as conn,conn.cursor() as cur:
        cur.execute("""update inventory_refresh_queue q set status='queued',requested_at=now(),
            attempt_count=0,metadata=q.metadata-'retry_base'-'pages_fetched'
            from sources s where s.source_id=q.source_id and s.enabled and s.adapter_status='live'
              and q.status='completed' and q.metadata ? 'model_discovery'
              and coalesce((q.metadata->>'last_success_at')::timestamptz,'epoch')
                  < now()-make_interval(mins=>coalesce(s.freshness_target_minutes,360))
              and exists(select 1 from source_adapters a where a.source_id=s.source_id and a.status='verified')""")
        count=cur.rowcount;conn.commit();return count


def seed_observed_models():
    """Learn model families from stored source observations, including old models.

    Historical evidence may identify a model, never establish current stock.
    Every resulting acquisition still fetches and verifies current listings.
    """
    with _connect() as conn,conn.cursor() as cur:
        cur.execute("""select v.brand,v.model,min(l.url) as evidence_url,
            max(l.last_verified_at) as model_observed_at
            from vehicles v join listings l using(vehicle_id) join sources s using(source_id)
            where s.metadata->>'parser_strategy' in ('cardekho_cards','cartrade_cards')
              and v.brand<>'' and v.model<>'' and l.last_verified_at is not null
            group by v.brand,v.model order by v.brand,v.model""")
        rows=cur.fetchall()
    groups={}
    for row in rows:
        groups.setdefault(row['brand'],[]).append({'model':row['model'],
            'evidence_url':row['evidence_url'],'discovery_kind':'observed_model',
            'model_observed_at':row['model_observed_at'].isoformat()})
    return sum(enqueue_models(brand,models) for brand,models in groups.items())
