"""One public request to a reviewed demo source; no registration or ingestion."""
import argparse
from collections import Counter
import json
import math
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

import yaml

from src import live_marketplaces as lm
from src.demo_dealers import parse_gurudev, parse_sundaram
from src.listing_evidence import SameOriginRedirect

SOURCES = {
    'Sundaram Motors Pre-Owned': ('sundaram_cards','https://sundarammotorspoc.com/listings/'),
    'Gurudev Tata Demo': ('gurudev_stock','https://gurudevtata.in/quotations/api/demo-stock/public'),
}
MAX_BYTES = min(lm.MAX_BODY_BYTES, 1_000_000)


class NoRedirect(SameOriginRedirect):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        # Even same-origin redirects would consume a second HTTP request.
        return None


def _source(name):
    if name not in SOURCES:
        raise ValueError('Unsupported probe source')
    config = Path(__file__).resolve().parents[1]/'config/sources.yaml'
    rows = yaml.safe_load(config.read_text(encoding='utf-8'))['known_sources']
    selected = [row for row in rows if row.get('name') == name]
    strategy,url = SOURCES[name]
    if len(selected) != 1 or selected[0].get('url') != url or selected[0].get('parser_strategy') != strategy:
        raise ValueError('Reviewed probe configuration changed')
    return selected[0]


def _sample_url(url,source):
    if not isinstance(url,str) or len(url)>2048 or any(c.isspace() for c in url):
        return None
    try:
        parts=urlsplit(url)
        origin=urlsplit(source['url'])
        approved_path=(bool(re.fullmatch(r'/listings/[a-zA-Z0-9_-]+/?',parts.path))
                       if source['parser_strategy']=='sundaram_cards' else parts.path=='/demo-cars.html')
        if (parts.scheme=='https' and parts.netloc==origin.netloc and not parts.username
                and not parts.password and not parts.query and not parts.fragment and approved_path):
            return url
    except ValueError:
        pass
    return None


def probe(source_name, *, opener=None):
    source = _source(source_name)
    report=dict(source=source_name,status='unavailable',reason='request_failed',
        maximum_requests=1,page_budget=1,retried=False,completeness_verified=False,
        absence_reconciliation_permitted=False,inventory_ingested=False,
        sampled_only=True,parsed_count=0,condition_counts={},samples=[])
    request=Request(source['url'],headers={'User-Agent':lm.USER_AGENT,
        'Accept':'application/json' if source['parser_strategy']=='gurudev_stock' else 'text/html'})
    try:
        with (opener or build_opener(NoRedirect())).open(request,timeout=10) as response:
            status=response.getcode()
            if not 200<=status<300:
                report.update(status='blocked' if status in (401,403,429) else 'unavailable',
                              reason='http_rejected',http_status=status)
                return report
            if response.geturl()!=source['url']:
                report['reason']='redirect_not_followed'
                return report
            report['http_status']=status
            raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:
                report['reason']='response_too_large'
                return report
            expected='application/json' if source['parser_strategy']=='gurudev_stock' else 'text/html'
            if expected not in response.headers.get('Content-Type','').lower():
                report['reason']='unsupported_content_type'
                return report
            body=raw.decode('utf-8','replace')
    except HTTPError as exc:
        report.update(status='blocked' if exc.code in (401,403,429) else 'unavailable',
                      reason='redirect_not_followed' if 300<=exc.code<400 else 'http_rejected',
                      http_status=exc.code)
        return report
    except Exception:
        return report
    token=lm._brand_identity_snapshot.set(tuple(source.get('brands') or []))
    try:
        rows=(parse_gurudev(body,source_name,source['url']) if source['parser_strategy']=='gurudev_stock'
              else parse_sundaram(body,source_name,source['url']))
        counts=Counter()
        samples=[]
        for row in rows:
            condition=row.get('condition_signal')
            if condition not in ('used','demo','unknown'):
                continue
            counts[condition]+=1
            price=row.get('price_lakh')
            url=_sample_url(row.get('url'),source)
            if (url and type(price) in (int,float) and math.isfinite(price) and price>0 and len(samples)<5):
                samples.append(dict(url=url,price_lakh=price,condition=condition))
        report.update(status='retrieved',reason='parsed_sample_not_inventory_guarantee',
                      parsed_count=len(rows),condition_counts=dict(counts),samples=samples)
    except Exception:
        report.update(status='parser_error',reason='parser_rejected_response')
    finally:
        lm._brand_identity_snapshot.reset(token)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,choices=tuple(SOURCES))
    args=parser.parse_args()
    print(json.dumps(probe(args.source),allow_nan=False))


if __name__=='__main__':
    main()
