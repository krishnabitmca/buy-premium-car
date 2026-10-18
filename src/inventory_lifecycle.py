"""Durable listing renewal, conservative removals and background health evidence."""
import argparse
import json
from uuid import uuid4
from datetime import datetime,timezone
from urllib.error import HTTPError
from urllib.parse import urlsplit
from .source_registry_db import _connect,require_database
from .inventory_freshness import global_expiry_minutes,expiry_sql
from . import crawl_leases
from .listing_evidence import fetch_listing,structured_evidence


def retire_catalogue_evidence(evidence,source_name,observed_at,conn):
    retired=0
    with conn.cursor() as cur:
        for item in evidence:
            cur.execute("""update listings l set status=%s,last_seen_at=now()
                from sources s where s.source_id=l.source_id and s.name=%s and l.url=%s
                and l.status in ('active','stale') and l.last_verified_at<=%s
                returning l.listing_id,l.vehicle_id,l.source_id""",
                ('sold' if item['reason'].startswith('sold') else 'removed',source_name,item['url'],observed_at))
            for row in cur.fetchall():
                cur.execute("""insert into vehicle_observations(vehicle_id,listing_id,source_id,observed_at,
                    live_verified,data_consistent,sold_signal,snapshot) values(%s,%s,%s,now(),false,true,true,%s::jsonb)""",
                    (row['vehicle_id'],row['listing_id'],row['source_id'],json.dumps(item)))
                retired+=1
    return retired


def maintain(limit=1000):
    """Expire offers without deleting history and enroll oldest individual URLs."""
    cap=global_expiry_minutes()
    with _connect() as conn,conn.cursor() as cur:
        cur.execute("""with expired as (
            select l.listing_id from listings l join sources s using(source_id) where l.status='active'
            and (l.last_verified_at is null or l.last_verified_at<now()-make_interval(mins=>"""+expiry_sql()+"""))
            order by l.last_verified_at asc nulls first,l.listing_id limit %s for update of l skip locked)
            update listings l set status='stale',freshness_state='expired'
            from expired e where e.listing_id=l.listing_id""",(cap,cap,max(1,min(int(limit),10000))))
        expired=cur.rowcount
        cur.execute("""insert into inventory_listing_refresh(listing_id,due_at)
            select l.listing_id,coalesce(l.last_verified_at,'epoch')+
                make_interval(mins=>least(s.freshness_target_minutes,case when l.condition='demo' then 180 else 360 end))
            from listings l join sources s using(source_id)
            where l.status in ('active','stale') and l.vehicle_id is not null and s.enabled and s.adapter_status='live'
            and exists(select 1 from source_adapters a where a.source_id=s.source_id and a.status='verified')
            and l.url ~ '^https?://' and rtrim(l.url,'/')<>rtrim(s.url,'/')
            and not exists(select 1 from listings other where other.source_id=l.source_id
                and other.url=l.url and other.listing_id<>l.listing_id)
            and not exists(select 1 from inventory_listing_refresh q where q.listing_id=l.listing_id)
            order by l.last_verified_at asc nulls first,l.listing_id limit %s
            on conflict do nothing""",(max(1,min(int(limit),10000)),))
        enrolled=cur.rowcount
        cur.execute("""update inventory_listing_refresh set status='queued',lease_token=null,
            lease_expires_at=null,last_error='worker lease expired',due_at=now()
            where status='running' and lease_expires_at<=now()""")
        recovered=cur.rowcount
        conn.commit()
    return {'expired':expired,'enrolled':enrolled,'recovered':recovered}


def claim(condition, *, listing_id=None):
    token=str(uuid4())
    with _connect() as conn,conn.cursor() as cur:
        cur.execute("""with requested as (select %s::uuid as target_id),picked as (
            select q.listing_id from inventory_listing_refresh q
            join listings l using(listing_id) join sources s using(source_id) cross join requested r
            where q.status in ('queued','failed','completed') and (q.due_at<=now() or q.listing_id=r.target_id)
              and (r.target_id is null or q.listing_id=r.target_id)
              and l.condition=%s and l.status in ('active','stale') and l.vehicle_id is not null and s.enabled and s.adapter_status='live'
              and exists(select 1 from source_adapters a where a.source_id=s.source_id and a.status='verified')
              and not exists(select 1 from inventory_crawl_leases d
                where d.domain=substring(lower(l.url) from '^https?://([^/:]+)')
                  and (d.lease_expires_at>now() or d.next_allowed_at>now()))
              and (q.listing_id=r.target_id or l.last_verified_at is null or l.last_verified_at<now()-make_interval(mins=>
                least(s.freshness_target_minutes,case when l.condition='demo' then 180 else 360 end)))
            order by q.due_at,q.listing_id for update of q skip locked limit 1)
            update inventory_listing_refresh q set status='running',lease_token=%s,
              lease_expires_at=now()+interval '30 minutes',attempt_count=attempt_count+1
            from picked p where q.listing_id=p.listing_id returning q.*""",(listing_id,condition,token))
        job=cur.fetchone()
        if job:
            cur.execute("""select l.*,l.metadata as listing_metadata,s.name as source_name,s.url as source_url,
                s.tier,s.freshness_target_minutes,v.brand,v.model,v.variant,v.manufacture_year,
                v.registration_year,v.fuel,v.transmission,v.metadata as vehicle_metadata,
                o.mileage_km,o.owner_count from listings l join sources s using(source_id)
                join vehicles v using(vehicle_id) left join lateral (
                    select mileage_km,owner_count from vehicle_observations where listing_id=l.listing_id
                    order by observed_at desc,observation_id desc limit 1) o on true
                where l.listing_id=%s""",(job['listing_id'],))
            job={**dict(cur.fetchone()),**dict(job)}
        conn.commit()
    return job


def finish(job,evidence):
    """Lease and canonical writes commit together; newer catalogue evidence wins."""
    with _connect() as conn,conn.cursor() as cur:
        cur.execute("""select * from inventory_listing_refresh where listing_id=%s and status='running'
            and lease_token=%s and lease_expires_at>now() for update""",(job['listing_id'],job['lease_token']))
        if not cur.fetchone():return False
        cur.execute('select vehicle_id,last_verified_at,status from listings where listing_id=%s for update',(job['listing_id'],))
        listing=cur.fetchone()
        outcome=evidence['outcome']
        if listing['last_verified_at']!=job['last_verified_at'] or listing['status'] not in {'active','stale'}:
            outcome='superseded'
        prior_missing=job['missing_count']
        if job['last_checked_at'] and job['last_verified_at'] and job['last_verified_at']>job['last_checked_at']:
            prior_missing=0  # A catalogue supplied positive evidence between disappearance checks.
        missing_count=prior_missing+1 if outcome=='missing' else 0
        if outcome=='available':
            from .inventory_ingestion import ingest_vehicles
            from .models import Vehicle
            meta=job['listing_metadata']
            ingest_vehicles([Vehicle(source_name=job['source_name'],source_tier=job['tier'],
                url=job['url'],final_url=job['final_url'],title=job['title'] or '',brand=job['brand'],model=job['model'],
                variant=job['variant'],year_manufacture=job['manufacture_year'],year_registration=job['registration_year'],
                mileage_km=job['mileage_km'],owner_count=job['owner_count'],fuel=job['fuel'],transmission=job['transmission'],
                seller_city=job['seller_city'],seller_state=job['seller_state'],condition_signal=job['condition'],
                vin=meta.get('vin'),chassis_number=meta.get('chassis_number'),source_listing_id=meta.get('source_listing_id'),
                price_basis=meta.get('price_basis'),body_type=meta.get('body_type'),image_urls=meta.get('image_urls') or [],
                price_lakh=evidence['price_lakh'],live_verified=True,data_consistent=True,
                verification_notes=['Exact listing JSON-LD offer: '+evidence['availability']])],_connection=conn)
            cur.execute("update listings set freshness_state='fresh' where listing_id=%s",(job['listing_id'],))
        elif outcome=='condition_unverified' and job['condition']=='demo':
            cur.execute("update listings set status='stale',freshness_state='stale' where listing_id=%s",(job['listing_id'],))
        elif outcome=='unavailable' or (outcome=='missing' and missing_count>=2):
            cur.execute("update listings set status='removed',last_seen_at=now() where listing_id=%s",(job['listing_id'],))
            cur.execute("""insert into vehicle_observations(vehicle_id,listing_id,source_id,observed_at,
                live_verified,data_consistent,sold_signal,snapshot) values(%s,%s,%s,now(),false,true,true,%s::jsonb)""",
                (job['vehicle_id'],job['listing_id'],job['source_id'],json.dumps(evidence)))
        success=outcome in {'available','unavailable','superseded'} or missing_count>=2
        failures=0 if success else job['failure_count']+1
        # Two 404/410 checks are separated by at least an hour. Errors never
        # renew last_verified_at. After five failures use a daily probation.
        delay=max(1,min(int(job['freshness_target_minutes']),180 if job['condition']=='demo' else 360)) if success else 60 if outcome=='missing' else min(360,15*2**min(failures,5))
        if failures>=5:delay=1440
        cur.execute("""update inventory_listing_refresh set status=%s,lease_token=null,lease_expires_at=null,
            due_at=now()+make_interval(mins=>%s),failure_count=%s,missing_count=%s,last_checked_at=now(),
            last_outcome=%s,last_error=%s where listing_id=%s and lease_token=%s""",
            ('completed' if success else 'failed',delay,failures,missing_count,outcome,evidence.get('error'),job['listing_id'],job['lease_token']))
        conn.commit()
    return True


def revalidate(job):
    url=job['url']
    if urlsplit(url).hostname!=urlsplit(job['source_url']).hostname:
        finish(job,{'outcome':'inconclusive','error':'Unapproved listing origin'})
        return 'inconclusive'
    lease=crawl_leases.acquire(url)
    if not lease:
        with _connect() as conn,conn.cursor() as cur:
            cur.execute("""update inventory_listing_refresh set status='queued',due_at=now()+interval '1 minute',
                attempt_count=attempt_count-1,lease_token=null,lease_expires_at=null
                where listing_id=%s and lease_token=%s""",(job['listing_id'],job['lease_token']))
            conn.commit()
        return 'deferred'
    delay=None
    try:
        try:
            html=fetch_listing(url)
            evidence=structured_evidence(html,url,job['brand'],job['model'],job['condition'])
        except HTTPError as exc:
            evidence={'outcome':'missing' if exc.code in {404,410} else 'error','http_status':exc.code,'error':'HTTP '+str(exc.code)}
            from .live_marketplaces import _canonical_url
            if _canonical_url(url,exc.url)!=_canonical_url(url,url):
                evidence={'outcome':'inconclusive','error':'Redirected error page is not disappearance evidence'}
            if exc.code in {403,429,503}:
                raw=exc.headers.get('Retry-After','') if exc.headers else ''
                delay=min(86400,max(60,int(raw))) if raw.isdigit() else 900
        except Exception as exc:
            evidence={'outcome':'error','error':type(exc).__name__}
        return evidence['outcome'] if finish(job,evidence) else 'superseded'
    finally:crawl_leases.release(lease,delay_seconds=delay)


def run_cycle(limit=10):
    require_database()
    run_id=str(uuid4())
    with _connect() as conn:
        prior=conn.execute('select max(started_at) as last_start from inventory_pipeline_runs').fetchone()['last_start']
        conn.execute('insert into inventory_pipeline_runs(run_id) values(%s)',(run_id,));conn.commit()
    summary={}
    try:
        summary=maintain()
        summary['heartbeat_gap_seconds']=int((datetime.now(timezone.utc)-prior).total_seconds()) if prior else None
        # Separate slots prevent used volume from starving demonstrator renewal.
        for i in range(max(1,min(int(limit),100))):
            job=claim('demo' if i%2==0 else 'used')
            if not job:continue
            outcome=revalidate(job);summary[outcome]=summary.get(outcome,0)+1
        status='degraded' if any(summary.get(k) for k in ('error','inconclusive','missing','condition_unverified')) or (summary['heartbeat_gap_seconds'] or 0)>3600 else 'ok'
    except Exception as exc:
        summary['fatal_error']=type(exc).__name__;status='failed'
        raise
    finally:
        with _connect() as conn:
            conn.execute('update inventory_pipeline_runs set completed_at=now(),status=%s,summary=%s::jsonb where run_id=%s',
                (status, json.dumps(summary),run_id));conn.commit()
    return summary


def report():
    with _connect() as conn,conn.cursor() as cur:
        cur.execute("""select s.name as source,l.condition,l.status,count(*) as offers,
            min(l.last_verified_at) as oldest_verified_at from listings l join sources s using(source_id)
            where s.enabled group by s.name,l.condition,l.status order by s.name,l.condition,l.status""")
        offers=[dict(r) for r in cur.fetchall()]
        cur.execute("""select q.status,q.last_outcome,count(*) as jobs,min(q.due_at) as oldest_due_at
            from inventory_listing_refresh q group by q.status,q.last_outcome""")
        queue=[dict(r) for r in cur.fetchall()]
        cur.execute("""select l.condition,count(*) as overdue_offers,min(q.due_at) as oldest_due_at
            from inventory_listing_refresh q join listings l using(listing_id) join sources s using(source_id)
            where l.status in ('active','stale') and s.enabled and q.due_at<now()
              and (l.last_verified_at is null or l.last_verified_at<now()-make_interval(mins=>
                least(s.freshness_target_minutes,case when l.condition='demo' then 180 else 360 end)))
            group by l.condition""")
        backlog=[dict(r) for r in cur.fetchall()]
        cur.execute('select * from inventory_pipeline_runs order by started_at desc limit 10')
        runs=[dict(r) for r in cur.fetchall()]
    return {'generated_at':datetime.now(timezone.utc).isoformat(),'offers':offers,'renewal_queue':queue,
        'overdue_by_condition':backlog,'recent_runs':runs,
        'heartbeat_late':not runs or (datetime.now(timezone.utc)-runs[0]['started_at']).total_seconds()>3600}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=10)
    parser.add_argument('--report')
    args=parser.parse_args()
    summary=run_cycle(args.limit)
    if (summary.get('heartbeat_gap_seconds') or 0)>3600:
        print('::warning::Inventory worker heartbeat gap exceeded one hour; freshness targets may be missed.')
    if args.report:
        from pathlib import Path
        path=Path(args.report);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report(),indent=2,default=str),encoding='utf-8')
    print(json.dumps(summary))


if __name__=='__main__':main()
