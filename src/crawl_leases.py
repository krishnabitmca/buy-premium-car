"""Short transactions fence background HTTP work across processes and sources."""
import os
from uuid import uuid4
from urllib.parse import urlsplit
from .source_registry_db import _connect


def acquire(url):
    domain=urlsplit(url).hostname
    if not domain or urlsplit(url).scheme not in {'http','https'}:
        raise ValueError('Invalid crawl origin')
    token=str(uuid4())
    with _connect() as conn,conn.cursor() as cur:
        cur.execute("""insert into inventory_crawl_leases(domain,lease_token,lease_expires_at)
            values(%s,%s,now()+interval '30 minutes') on conflict(domain) do update
            set lease_token=excluded.lease_token,lease_expires_at=excluded.lease_expires_at
            where inventory_crawl_leases.lease_expires_at<=now()
              and inventory_crawl_leases.next_allowed_at<=now() returning domain""",(domain,token))
        acquired=cur.fetchone() is not None
        conn.commit()
    return (domain,token) if acquired else None


def release(lease, *, delay_seconds=None):
    if not lease:return
    delay=max(0,min(int(delay_seconds if delay_seconds is not None else os.getenv('CARSCANNER_CRAWL_DELAY_SECONDS','5')),86400))
    with _connect() as conn,conn.cursor() as cur:
        cur.execute("""update inventory_crawl_leases set lease_expires_at=now(),
            next_allowed_at=now()+make_interval(secs=>%s) where domain=%s and lease_token=%s""",
            (delay,*lease))
        conn.commit()
