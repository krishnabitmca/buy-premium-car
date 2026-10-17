"""Discover reviewed, advertised catalogue scopes; never construct city URLs."""
import re
from urllib.parse import urljoin,urlsplit,parse_qs
from bs4 import BeautifulSoup
from .source_registry_db import _connect


def advertised_scopes(html,source,base_url):
    config={**(source.get('metadata') or {}),**source}
    city_path=config.get('city_catalog_path_pattern')
    city_title=config.get('city_catalog_title_pattern')
    catalogue=config.get('catalogue_link_pattern')
    if not (city_path and city_title or catalogue):return []
    found={}
    for anchor in BeautifulSoup(html,'html.parser').select('a[href]'):
        url=urljoin(base_url,anchor['href']);parts=urlsplit(url)
        if parts.scheme not in {'https','http'} or parts.hostname!=urlsplit(base_url).hostname or parts.query or parts.fragment:continue
        title=' '.join(anchor.get('title','').split())
        if city_path and city_title and re.fullmatch(city_path,parts.path):
            match=re.fullmatch(city_title,title)
            if match:
                found[url.rstrip('/')]=dict(url=url.rstrip('/'),kind='city',label=match[1],discovered_from=base_url)
        if catalogue and re.fullmatch(catalogue,parts.path):
            found[url.rstrip('/')]=dict(url=url.rstrip('/'),kind='dealer_catalogue',label=anchor.get_text(' ',strip=True),discovered_from=base_url)
    return list(found.values())[:200]


def advertised_total(html):
    soup=BeautifulSoup(html,'html.parser')
    heading=soup.find('h1')
    if heading:
        match=re.match(r'^([\d,]+)\s+(?:Used|Second Hand)\b',heading.get_text(' ',strip=True),re.I)
        if match:return int(match[1].replace(',',''))
    return None


def validate_paged_response(html, url):
    """WordPress may redirect page two back to page one without an HTTP error."""
    requested=parse_qs(urlsplit(url).query).get('paged', [])
    current=BeautifulSoup(html,'html.parser').select_one('.page-numbers.current')
    if requested and requested[0].isdigit() and current:
        shown=current.get_text(strip=True)
        if shown.isdigit() and int(shown)!=int(requested[0]):
            raise ValueError('Source pagination stalled: requested page '+requested[0]+' but source returned page '+shown)


def wake_catalogues():
    """Bootstrap newly reviewed scope discovery without resetting active scans."""
    with _connect() as conn,conn.cursor() as cur:
        cur.execute("""update inventory_refresh_queue q set status='queued',requested_at=now(),attempt_count=0
            from sources s where s.source_id=q.source_id and s.enabled and s.adapter_status='live'
            and (s.metadata ? 'city_catalog_path_pattern' or s.metadata ? 'catalogue_link_pattern')
            and q.brand='' and q.model='' and q.destination_state='' and q.condition='both' and q.status='completed'
            and not(q.metadata ? 'last_scan_evidence')
            and exists(select 1 from source_adapters a where a.source_id=s.source_id and a.status='verified')""")
        count=cur.rowcount;conn.commit();return count
