"""Private operational coverage evidence. No crawl or customer request runs here."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import math
from urllib.parse import urlsplit

from .inventory_db import eligibility_predicates, eligibility_checks
from .inventory_freshness import global_expiry_minutes
from .source_registry_db import _connect, require_database
from .india_geo import normalize_seller_location


def _iso(value):
    return value.isoformat() if isinstance(value,datetime) else value


def _tokens(value):
    from .live_marketplaces import _identity_tokens
    return ' '.join(_identity_tokens(value))


def _brand(value):
    from .live_marketplaces import _canonical_brand
    return _canonical_brand(str(value or '')).strip()


def _condition_support(source,condition):
    values=set(source.get('conditions') or [])
    return not values or condition=='both' or bool(values & {condition,'all','both'})


def summarize(facts,sources,jobs,runs,*,now=None,renewal_limit=10,interval_minutes=15):
    """Sparse dimensions are evidence, never an invented brand×city catalogue."""
    now=now or datetime.now(timezone.utc)
    if not 1<=renewal_limit<=100 or not 1<=interval_minutes<=1440:
        raise ValueError('Invalid capacity scenario')
    source_map={s['source']:s for s in sources}
    matrix={}
    source_stats=defaultdict(lambda:Counter())
    renewal=defaultdict(lambda:Counter())
    identities=defaultdict(set)
    source_vehicles=defaultdict(set)
    city_cells={};city_vehicles=defaultdict(set)
    exclusions=defaultdict(Counter)
    shared_urls=Counter((r['source'],r['url']) for r in facts)
    for row in facts:
        source=row['source'];condition=row.get('condition') or 'unknown'
        brand=_brand(row.get('brand'));model=str(row.get('model') or '').strip()
        city=str(row.get('seller_location_label') or '').strip() or None
        location=normalize_seller_location(city)
        key=(source,city,_tokens(brand),_tokens(model),condition)
        cell=matrix.setdefault(key,dict(source=source,seller_location_label=city,
            **location,
            brand=brand,model=model,condition=condition,observed_offers=0,eligible_offers=0,
            excluded_offers=0,exclusion_reasons=Counter(),last_verified_at=None))
        cell['observed_offers']+=1
        stat=source_stats[source];stat['observed_offers']+=1
        timestamp=row.get('last_verified_at')
        if timestamp and (not cell['last_verified_at'] or timestamp>cell['last_verified_at']):
            cell['last_verified_at']=timestamp
        if row.get('eligible'):
            cell['eligible_offers']+=1;stat['eligible_offers']+=1
            identity=(str(row['vehicle_id']),row.get('price_basis') or 'unspecified')
            identities[key].add(identity);source_vehicles[source].add(identity)
            city_key=(source,location['canonical_city'],location['canonical_state'],condition,location['location_status'])
            city_cell=city_cells.setdefault(city_key,dict(source=source,**location,condition=condition,
                eligible_offers=0,seller_location_labels=set()))
            city_cell['eligible_offers']+=1
            if city:city_cell['seller_location_labels'].add(city)
            city_vehicles[city_key].add(identity)
        else:
            cell['excluded_offers']+=1;stat['excluded_offers']+=1
            reasons=set(row.get('exclusion_reasons') or ['unclassified_exclusion'])
            cell['exclusion_reasons'].update(reasons);exclusions[source].update(reasons)
        if row.get('status') not in {'active','stale'}:continue
        if row.get('listing_condition') not in {'used','demo'}:
            stat['needs_classification']+=1;continue
        configured=source_map.get(source,{})
        if not configured.get('enabled') or not configured.get('verified') or configured.get('adapter_status')!='live':continue
        url=urlsplit(row['url']);root=urlsplit(configured.get('url') or '')
        if (url.scheme not in {'http','https'} or url.hostname!=root.hostname or
                row['url'].rstrip('/')==str(configured.get('url') or '').rstrip('/') or shared_urls[source,row['url']]>1):
            stat['catalogue_or_origin_review_only']+=1;continue
        c=row['listing_condition'];target=max(1,min(int(configured.get('target_minutes') or 360),180 if c=='demo' else 360))
        demand=renewal[c];demand['renewable_offers']+=1
        demand['individual_checks_per_hour']+=60/target
        overdue=not timestamp or (now-timestamp).total_seconds()>target*60
        if overdue:demand['overdue_offers']+=1;stat['overdue_offers']+=1
        if not row.get('renewal_status'):demand['not_enrolled']+=1
        if row.get('renewal_status') in {'queued','completed','failed'} and row.get('due_at') and row['due_at']<=now and overdue:
            demand['ready_jobs']+=1
        if row.get('renewal_status')=='failed':demand['failed_jobs']+=1
        if row.get('last_outcome') in {'inconclusive','condition_unverified'}:stat['detail_parser_gaps']+=1
    cells=[]
    for key,cell in matrix.items():
        cell['eligible_vehicles']=len(identities[key])
        cell['status']='partial_observed' if cell['eligible_offers'] else 'no_current_eligible_observation'
        cell['last_verified_at']=_iso(cell['last_verified_at'])
        cell['market_coverage_percent']=None
        cell['exclusion_reasons']=dict(cell['exclusion_reasons'])
        cells.append(cell)

    declared=[];scope_seen=set();priorities={}
    def scope(source,kind,label,url,brand='',model='',condition='both',status='unknown',advertised=None,attempted=False,job=None):
        key=(source,kind,url,_tokens(brand),_tokens(model),condition)
        if key in scope_seen:return
        scope_seen.add(key)
        job=job or {}
        declared.append(dict(source=source,scope_kind=kind,label=label,evidence_url=url,
            **(normalize_seller_location(label) if kind=='city' else {}),
            brand=brand or None,model=model or None,condition=condition,
            traversal_status=status,attempted=attempted,advertised_count=advertised,
            job_status=job.get('status'),last_attempt_at=_iso(job.get('started_at')),
            last_attempt_failed=bool(job.get('last_error') or job.get('status')=='failed'),
            advertised_count_is_verified_stock=False,market_coverage_percent=None))
    for source in sources:
        name=source['source'];stat=source_stats[name]
        priorities[name]=dict(source=name,enabled=source.get('enabled'),adapter_status=source.get('adapter_status'),
            adapter_verified=source.get('verified'),parser=source.get('parser'),
            declared_conditions=source.get('conditions') or [],
            **{k:stat[k] for k in ('observed_offers','eligible_offers','excluded_offers','overdue_offers',
                'needs_classification','detail_parser_gaps','catalogue_or_origin_review_only')},
            eligible_vehicles=len(source_vehicles[name]),pending_pages=0,failed_jobs=0,
            exclusion_reasons=dict(exclusions[name]),queued_jobs=0,running_jobs=0,
            oldest_queued_hours=None,oldest_running_hours=None,
            last_batch_yield=None,actions=[])
        scope(name,'source_root',None,source.get('url'),status='not_measured')
    latest_catalogue={}
    job_totals=Counter()
    jobs=sorted(jobs,key=lambda row:row.get('started_at') or datetime.min.replace(tzinfo=timezone.utc),reverse=True)
    for job in jobs:
        name=job['source'];priority=priorities.get(name)
        if not priority:continue
        job_totals[job['status']]+=1
        if job['status'] in {'queued','running'}:
            priority[job['status']+'_jobs']+=1
            stamp=job.get('requested_at') if job['status']=='queued' else job.get('started_at')
            if stamp:
                age=round(max(0,(now-stamp).total_seconds()/3600),2)
                field='oldest_'+job['status']+'_hours'
                priority[field]=max(priority[field] or 0,age)
        if job['status']=='failed' or job.get('last_error'):priority['failed_jobs']+=1
        evidence=job.get('scan_evidence') or {}
        cursor=job.get('continuation') or {}
        state=evidence.get('coverage_state') or ('not_attempted' if not job.get('started_at') else 'unmeasured_attempt')
        condition=job.get('condition') or 'both'
        if not _condition_support(source_map[name],condition):state='condition_not_declared'
        scope(name,'model' if job.get('model') else 'make' if job.get('brand') else 'global',None,
            job.get('model_evidence_url') or source_map[name].get('url'),
            _brand(job.get('brand')),job.get('model') or '',condition,state,
            job.get('advertised_model_count'),bool(job.get('started_at')),job)
        for advertised in evidence.get('catalog_scopes') or []:
            url=advertised.get('url')
            visited=set(cursor.get('visited_urls') or [])
            attempted=url in visited or state=='traversal_exhausted_unverified'
            # A visited category is only a visited page, not a completed city.
            scope(name,advertised.get('kind') or 'advertised_catalogue',advertised.get('label'),url,
                condition=condition,status='page_visited_completeness_unknown' if attempted else 'discovered_unvisited',
                advertised=(evidence.get('advertised_counts') or {}).get(url),attempted=attempted,job=job)
        pending=evidence.get('pending_page_count')
        if isinstance(pending,int):priority['pending_pages']+=pending
        if not job.get('brand') and not job.get('model') and condition=='both':latest_catalogue.setdefault(name,job)
    for name,priority in priorities.items():
        job=latest_catalogue.get(name,{})
        evidence=job.get('scan_evidence') or {}
        pages=evidence.get('pages_this_batch');offers=evidence.get('listings_this_batch')
        if isinstance(pages,int) and pages>0 and isinstance(offers,int):
            priority['last_batch_yield']=dict(pages=pages,offers=offers,offers_per_page=round(offers/pages,2),
                measured_at=_iso(job.get('batch_observed_at')),is_latest_batch_only=True)
        if not priority['adapter_verified'] or not priority['parser']:priority['actions'].append('review_adapter_or_provider_feed')
        if priority['failed_jobs']:priority['actions'].append('inspect_source_failures')
        if priority['pending_pages']:priority['actions'].append('resume_advertised_catalogues')
        if priority['detail_parser_gaps']:priority['actions'].append('review_detail_evidence_parser')
        if priority['needs_classification']:priority['actions'].append('obtain_used_demo_classification_evidence')
        if not priority['eligible_offers']:priority['actions'].append('establish_current_inventory_coverage')
        if priority['exclusion_reasons'].get('verification_expired_or_missing'):
            priority['actions'].append('restore_current_verification_evidence')
        if not priority['enabled']:
            priority['actions'].insert(0,'operator_disabled_do_not_schedule')
        priority['score']=priority['pending_pages']*2+priority['overdue_offers']+priority['detail_parser_gaps']*5

    capacity=[]
    for condition in ('used','demo'):
        demand=renewal[condition]
        slots=(renewal_limit+1)//2 if condition=='demo' else renewal_limit//2
        hourly=slots*60/interval_minutes
        required=demand['individual_checks_per_hour']
        capacity.append(dict(condition=condition,renewable_offers=demand['renewable_offers'],
            overdue_offers=demand['overdue_offers'],ready_jobs=demand['ready_jobs'],not_enrolled=demand['not_enrolled'],
            individual_check_demand_per_hour=round(required,2),reserved_attempt_capacity_per_hour=round(hourly,2),
            theoretical_capacity_ratio=round(hourly/required,4) if required else None,
            equivalent_reserved_budgets=math.ceil(required/hourly) if hourly and required else None,
            minimum_backlog_hours_at_reserved_budget=round(demand['overdue_offers']/hourly,2) if hourly else None))
    outcomes=Counter();duration=0;completed=0
    for run in runs:
        summary=run.get('summary') or {}
        for key in ('available','unavailable','inconclusive','condition_unverified','missing','error','deferred','superseded'):
            outcomes[key]+=int(summary.get(key) or 0)
        if run.get('completed_at'):
            completed+=1;duration+=max(0,(run['completed_at']-run['started_at']).total_seconds())
    return dict(generated_at=now.isoformat(),snapshot_at=now.isoformat(),scope='india',complete_market_coverage=False,
        city_coverage=[dict(**cell,eligible_vehicles=len(city_vehicles[key])) | {'seller_location_labels':sorted(cell['seller_location_labels'])}
            for key,cell in sorted(city_cells.items(),key=lambda pair:tuple(value or '' for value in pair[0]))],
        coverage_matrix=sorted(cells,key=lambda r:(r['source'],r['seller_location_label'] or '',r['brand'],r['model'],r['condition'])),
        declared_scopes=declared,source_priorities=sorted(priorities.values(),key=lambda r:(-r['score'],r['source'])),
        acquisition_queue=dict(job_totals),capacity=dict(assumed_interval_minutes=interval_minutes,renewal_attempts_per_cycle=renewal_limit,
            conditions=capacity,recorded_runs_last24h=len(runs),completed_runs_last24h=completed,
            recorded_outcomes_last24h=dict(outcomes),mean_completed_run_seconds=round(duration/completed,2) if completed else None,
            assumptions=['Configured cadence is hypothetical; recorded runs include manual executions.',
                'Demand is an individual-check scenario. Catalogue batches can renew many offers per request.',
                'Attempt budgets are not successful verification rates or a worker/server purchase recommendation.',
                'Origin pacing, parser failures and scheduler delays reduce usable capacity; idle condition slots may be borrowed.']),
        definitions=dict(location='Raw source seller labels are preserved. Canonical city/state accepts known labels and matching state suffixes only; unresolved regions/addresses remain unknown. Never a buyer destination boundary.',
            sparse_matrix='Observed dimensions only. Missing combinations and unvisited scopes have unknown coverage.',
            pending_pages='Pending page slots across jobs can overlap; they are not unique vehicles or market size.',
            advertised_counts='Source claims may overlap and may include stale stock; never summed into a national denominator.',
            eligibility='Uses customer search offer eligibility and the actual latest observation.',
            exclusion_reasons='Failed canonical eligibility checks; multiple reasons may apply to one offer. Counts are not additive. Missing observations fail closed.',
            queue_age='Elapsed time since latest queue request or running claim, including cooldown and dispatch delays; not a predicted completion time or confirmed stuck job.',
            completeness='No independent eligible-listing benchmark has established market coverage percentages.'))


def operations_report(*,renewal_limit=10,interval_minutes=15):
    require_database()
    cap=global_expiry_minutes()
    eligible=' and '.join(eligibility_predicates())
    checks={**eligibility_checks(),'observation_vehicle_mismatch': 'o.vehicle_id=v.vehicle_id'}
    reasons='array_remove(array['+','.join(
        "case when ("+predicate+") is not true then '"+name+"' end"
        for name,predicate in checks.items())+'],NULL)'
    with _connect() as conn,conn.cursor() as cur:
        cur.execute('set transaction isolation level repeatable read read only')
        cur.execute('select now() as now');now=cur.fetchone()['now']
        cur.execute("""select s.name as source,s.url,s.enabled,s.adapter_status,s.freshness_target_minutes as target_minutes,
            s.metadata->>'parser_strategy' as parser,
            exists(select 1 from source_adapters a where a.source_id=s.source_id and a.status='verified') as verified,
            array(select lower(capability_value) from source_capabilities sc where sc.source_id=s.source_id
                and sc.capability_type='condition') as conditions from sources s order by s.name""")
        sources=[dict(r) for r in cur.fetchall()]
        cur.execute("""select s.name as source,l.listing_id,l.url,l.status,l.condition as listing_condition,
            v.vehicle_id,v.brand,v.model,v.condition,l.last_verified_at,
            coalesce(nullif(trim(l.seller_city),''),nullif(trim(v.seller_city),'')) as seller_location_label,
            coalesce(o.snapshot->>'price_basis','unspecified') as price_basis,
            coalesce(("""+eligible+""" and o.vehicle_id=v.vehicle_id),false) as eligible,
            """+reasons+""" as exclusion_reasons,
            r.status as renewal_status,r.due_at,r.last_outcome
            from listings l join vehicles v using(vehicle_id)
            left join lateral(select observation.* from vehicle_observations observation where observation.listing_id=l.listing_id
                order by observed_at desc,observation_id desc limit 1) o on true
            join sources s on s.source_id=coalesce(o.source_id,l.source_id)
            left join inventory_listing_refresh r on r.listing_id=l.listing_id""",(cap,cap,cap,cap))
        facts=[dict(r) for r in cur.fetchall()]
        cur.execute("""select s.name as source,q.brand,q.model,q.condition,q.status,q.requested_at,q.started_at,q.completed_at,q.last_error,
            q.metadata->'last_scan_evidence' as scan_evidence,q.metadata->'continuation' as continuation,
            q.metadata->'advertised_model_count' as advertised_model_count,
            q.metadata->>'last_batch_observed_at' as batch_observed_at,
            q.metadata->'model_discovery'->>'evidence_url' as model_evidence_url
            from inventory_refresh_queue q join sources s using(source_id)
            order by q.requested_at,q.refresh_id""")
        jobs=[dict(r) for r in cur.fetchall()]
        cur.execute("""select started_at,completed_at,status,summary from inventory_pipeline_runs
            where started_at>=now()-interval '24 hours' order by started_at""")
        runs=[dict(r) for r in cur.fetchall()]
    return summarize(facts,sources,jobs,runs,now=now,renewal_limit=renewal_limit,interval_minutes=interval_minutes)


def markdown_report(report):
    lines=['# Inventory coverage operations', '', 'Generated: '+report['generated_at'], '',
        'Coverage remains unknown outside observed dimensions and declared scopes. No market-wide percentage is established.', '',
        '| Condition | Renewable offers | Overdue | Individual checks/hour needed | Reserved attempts/hour |',
        '| --- | ---: | ---: | ---: | ---: |']
    for row in report['capacity']['conditions']:
        lines.append('| {condition} | {renewable_offers} | {overdue_offers} | {individual_check_demand_per_hour} | {reserved_attempt_capacity_per_hour} |'.format(**row))
    lines+=['','These are individual-check scenarios, not worker purchase recommendations. Bulk catalogue refresh, parser yield, origin limits and actual scheduling determine real capacity.','',
        '| Source | Eligible offers | Pending pages | Overdue offers | Actions |','| --- | ---: | ---: | ---: | --- |']
    for row in report['source_priorities']:
        safe={**row,'source':row['source'].replace('|',' '),'actions':', '.join(row['actions']) or 'maintain_and_measure'}
        lines.append('| {source} | {eligible_offers} | {pending_pages} | {overdue_offers} | {actions} |'.format(**safe))
    lines+=['','| Source | Exclusion reason | Offers |','| --- | --- | ---: |']
    for row in report['source_priorities']:
        for reason,count in sorted(row.get('exclusion_reasons',{}).items()):
            lines.append('| '+row['source'].replace('|',' ')+' | '+reason+' | '+str(count)+' |')
    lines+=['','An offer can have multiple exclusion reasons; these counts must not be summed.', '',
        '| Source | Queued | Oldest queued hours | Running | Oldest running hours |',
        '| --- | ---: | ---: | ---: | ---: |']
    for row in report['source_priorities']:
        safe={**row,'source':row['source'].replace('|',' '),
            'oldest_queued_hours':row.get('oldest_queued_hours') if row.get('oldest_queued_hours') is not None else 'Unknown',
            'oldest_running_hours':row.get('oldest_running_hours') if row.get('oldest_running_hours') is not None else 'Unknown'}
        lines.append('| {source} | {queued_jobs} | {oldest_queued_hours} | {running_jobs} | {oldest_running_hours} |'.format(**safe))
    lines+=['','Queue ages include pacing and dispatch delays; they do not by themselves prove a stuck worker. Disabled sources remain visible for operator review.']
    lines+=['','| Source | Canonical city | State | Condition | Eligible offers | Eligible vehicles |',
        '| --- | --- | --- | --- | ---: | ---: |']
    for cell in report.get('city_coverage',[]):
        row={**cell,'canonical_city':cell['canonical_city'] or 'Unknown ('+cell['location_status']+')',
             'canonical_state':cell['canonical_state'] or 'Unknown'}
        row={key:str(value).replace('|',' ').replace('\n',' ') for key,value in row.items()}
        lines.append('| {source} | {canonical_city} | {canonical_state} | {condition} | {eligible_offers} | {eligible_vehicles} |'.format(**row))
    lines+=['','City aliases are combined only from recognized labels. Addresses and regions remain unresolved. Vehicles can appear in multiple rows; do not sum rows into a national unique-car count.']
    return '\n'.join(lines)+'\n'
