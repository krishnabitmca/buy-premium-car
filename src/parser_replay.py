"""Bounded historical Fusion parser samples; never ingestion or availability."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re
from urllib.parse import urljoin, urlsplit
from uuid import UUID

from bs4 import BeautifulSoup

from . import live_marketplaces as lm
from .listing_evidence import catalogue_tombstones
from .reviewed_inventory import parse_reviewed_cards

MAX_INPUT_BYTES=1_048_576
MAX_ARTIFACT_BYTES=65_536
VERSION=1
PARSER_VERSION='fusion_cards-v1'
SANITIZER_VERSION='fusion-allowlist-v1'
_SENSITIVE=re.compile(r'@|https?://|\b(?:token|session|cookie|secret|password|authorization|bearer|email|phone|contact|csrf|api[_ -]?key)(?:\b|_)',re.I)
_PHONE=re.compile(r'(?:\+?\d[\s().-]*){9,}')


def _encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def _hash(value):
    return sha256(value).hexdigest()


def _url(value, catalogue=False):
    if not isinstance(value,str) or len(value)>512 or any(c.isspace() for c in value):
        raise ValueError('Unsafe source URL')
    parts=urlsplit(value)
    pattern=r'/(?:collections/|brand/[a-z0-9-]+/?)' if catalogue else r'/cars/[a-zA-Z0-9_-]+/?'
    if (parts.scheme!='https' or parts.netloc!='fusioncars.in' or parts.username or parts.password
            or parts.query or parts.fragment or not re.fullmatch(pattern,parts.path)
            or _PHONE.search(parts.path)
            or _SENSITIVE.search(parts.path)
            or re.search(r'(?:token|session|secret|password|reset|auth|email|phone)',parts.path,re.I)):
        raise ValueError('Unsafe source URL')
    return value


def _taxonomy(names):
    allowed=set(lm.CAR_MAKES)|set(lm.BRAND_ALIASES)|set(lm.BRAND_ALIASES.values())
    if names is None:names=sorted(allowed)
    if not isinstance(names,(list,tuple)) or not 1<=len(names)<=200:
        raise ValueError('Invalid taxonomy')
    if any(not isinstance(name,str) or name not in allowed for name in names):
        raise ValueError('Invalid taxonomy')
    return sorted(set(names))


def _text(node, limit=120):
    if node is None:return ''
    value=' '.join(node.get_text(' ',strip=True).split())
    if (len(value)>limit or _SENSITIVE.search(value) or _PHONE.search(value)
            or not re.fullmatch(r'[\w\s₹.,()/+&-]*',value,re.UNICODE)):
        raise ValueError('Unsafe automotive field')
    return value


def _sanitize(html,base):
    soup=BeautifulSoup(html,'html.parser')
    for node in soup.select('script,style,form,template,iframe,object'):node.decompose()
    cards=soup.select('.product[data-price][data-features]')
    output=BeautifulSoup('','html.parser')
    accepted=0
    for card in cards[:5]:
        try:
            anchor=card.select_one('a[href]')
            if anchor is None:continue
            url=_url(urljoin(base,anchor.get('href','')))
            brand=card.get('data-features','')
            if not isinstance(brand,str) or brand not in _taxonomy(None):continue
            title=_text(card.select_one('.car_heading h5'))
            price=_text(card.select_one('.car-price'),48)
            rawprice=card.get('data-price','')
            if not re.fullmatch(r'\d{1,9}(?:\.\d{1,2})?',rawprice):continue
            if not title or not price or not re.fullmatch(r'(?:₹|Rs\.?|INR)?\s*[\d,. ]+(?:\s*(?:lakh|lakhs|crore|crores|L|Cr))?',price,re.I):continue
            wrapper=output.new_tag('div',attrs={'class':'product','data-price':rawprice,'data-features':brand})
            link=output.new_tag('a',href=url);wrapper.append(link)
            heading=output.new_tag('div',attrs={'class':'car_heading'})
            h5=output.new_tag('h5');h5.string=title;heading.append(h5);link.append(heading)
            amount=output.new_tag('div',attrs={'class':'car-price'});amount.string=price;link.append(amount)
            info=output.new_tag('div',attrs={'class':'car_info'})
            for item in card.select('.car_info li'):
                key=_text(item.select_one('h6'),16).lower()
                if key not in ('kms','registered','fuel'):continue
                value=_text(item.select_one('.asert'),24)
                if key=='kms' and not re.fullmatch(r'[\d,]{1,9}',value):continue
                if key=='registered' and not re.fullmatch(r'(?:19|20)\d{2}',value):continue
                if key=='fuel' and value.casefold() not in ('petrol','diesel','hybrid','electric','cng','lpg'):continue
                li=output.new_tag('li');label=output.new_tag('h6');label.string=key
                field=output.new_tag('span',attrs={'class':'asert'});field.string=value
                li.extend([label,field]);info.append(li)
            link.append(info)
            visible=' '.join(card.stripped_strings)
            marker=re.search(r'\b(sold(?: out)?|booked|reserved|no longer available)\b',visible,re.I)
            if marker:
                badge=output.new_tag('span');badge.string=marker[0].lower();link.append(badge)
            output.append(wrapper);accepted+=1
        except (ValueError,TypeError):
            # A risky selected field invalidates the sample; do not silently
            # present the remaining cards as the same sanitized selection.
            return '',0,len(cards)>5
    return str(output),accepted,len(cards)>5


def _extract(html,source_name,source_url,taxonomy):
    token=lm._brand_identity_snapshot.set(tuple(taxonomy))
    try:
        rows=parse_reviewed_cards(html,source_name,source_url,'fusion_cards')
        positives=[]
        keys=('source_listing_id','url','brand','model','price_lakh','km','registration_year','condition_signal')
        for row in rows:
            if any(isinstance(row.get(k),float) and not math.isfinite(row[k]) for k in keys):
                raise ValueError('Nonfinite normalized output')
            positives.append({key:row.get(key) for key in keys})
        negatives=[{'url':row['url'],'reason':row['reason']} for row in catalogue_tombstones(html,source_url,'fusion_cards')]
        return {'positive':positives,'explicit_negative':negatives}
    finally:lm._brand_identity_snapshot.reset(token)


def _context(source_name,source_url,brand_names,scan_generation,captured_at):
    _url(source_url,True)
    if source_name not in ('Fusion Cars','Fusion','Fusion Cars India'):
        raise ValueError('Unsupported source identity')
    taxonomy=_taxonomy(brand_names)
    if scan_generation is not None:scan_generation=str(UUID(str(scan_generation)))
    stamp=datetime.now(timezone.utc) if captured_at is None else captured_at
    if isinstance(stamp,str):stamp=datetime.fromisoformat(stamp.replace('Z','+00:00'))
    if not isinstance(stamp,datetime) or stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('Capture timestamp requires timezone')
    return taxonomy,scan_generation,stamp.astimezone(timezone.utc)


def capture_sample(html,*,source_name='Fusion Cars',source_url,strategy='fusion_cards',
                   brand_names=None,scan_generation=None,captured_at=None):
    result={'status':'no_supported_cards','historical_sample':True,'sampled_only':True,
            'completeness_verified':False,'absence_reconciliation_permitted':False}
    if strategy!='fusion_cards':return {**result,'status':'unsupported_strategy'}
    if not isinstance(html,(str,bytes)):raise ValueError('HTML must be text or UTF-8 bytes')
    raw=html if isinstance(html,bytes) else html.encode('utf-8')
    if len(raw)>MAX_INPUT_BYTES:return {**result,'status':'input_oversized'}
    if isinstance(html,bytes):html=html.decode('utf-8')
    taxonomy,scan_generation,stamp=_context(source_name,source_url,brand_names,scan_generation,captured_at)
    clean,count,limited=_sanitize(html,source_url)
    if not count:return result
    expected=_extract(clean,source_name,source_url,taxonomy)
    # Sanitizable markup alone is not proof that the reviewed parser supports
    # this sample. Preserve unavailable evidence instead of a vacuous match.
    if not expected['positive'] and not expected['explicit_negative']:
        return result
    artifact={**result,'status':'captured_sample','version':VERSION,'parser_version':PARSER_VERSION,
        'sanitizer_version':SANITIZER_VERSION,'strategy':strategy,'source_name':source_name,
        'source_url':source_url,'captured_at':stamp.astimezone(timezone.utc).isoformat(),
        'scan_generation':scan_generation,'brand_names':taxonomy,'selection_limited':limited,
        'sample_count':count,'html':clean,'input_sha256':_hash(raw),'html_sha256':_hash(clean.encode()),
        'expected':expected,'expected_sha256':_hash(_encoded(expected))}
    if len(_encoded(artifact))>MAX_ARTIFACT_BYTES:return {**result,'status':'sample_oversized'}
    return artifact


def replay_sample(artifact):
    unavailable={'status':'replay_unavailable','historical_sample':True,'sampled_only':True,
                 'completeness_verified':False,'absence_reconciliation_permitted':False}
    try:
        if not isinstance(artifact,dict) or len(_encoded(artifact))>MAX_ARTIFACT_BYTES:return unavailable
        allowed={'status','historical_sample','sampled_only','completeness_verified','absence_reconciliation_permitted',
            'version','parser_version','sanitizer_version','strategy','source_name','source_url','captured_at',
            'scan_generation','brand_names','selection_limited','sample_count','html','input_sha256','html_sha256',
            'expected','expected_sha256'}
        if set(artifact)!=allowed or artifact['status']!='captured_sample' or type(artifact['version']) is not int or artifact['version']!=VERSION:return unavailable
        if artifact['parser_version']!=PARSER_VERSION or artifact['sanitizer_version']!=SANITIZER_VERSION:return unavailable
        if (artifact['historical_sample'] is not True or artifact['sampled_only'] is not True
                or artifact['completeness_verified'] is not False or artifact['absence_reconciliation_permitted'] is not False):return unavailable
        if type(artifact['selection_limited']) is not bool or type(artifact['sample_count']) is not int or not 1<=artifact['sample_count']<=5:return unavailable
        if any(not isinstance(artifact[k],str) or not re.fullmatch('[0-9a-f]{64}',artifact[k]) for k in ('input_sha256','html_sha256','expected_sha256')):return unavailable
        if _hash(artifact['html'].encode())!=artifact['html_sha256'] or _hash(_encoded(artifact['expected']))!=artifact['expected_sha256']:return unavailable
        if artifact['strategy']!='fusion_cards' or not isinstance(artifact['captured_at'],str):return unavailable
        taxonomy,_,_=_context(artifact['source_name'],artifact['source_url'],artifact['brand_names'],
                            artifact['scan_generation'],artifact['captured_at'])
        clean,count,_=_sanitize(artifact['html'],artifact['source_url'])
        if not count or clean!=artifact['html'] or count!=artifact['sample_count']:return unavailable
        # Never echo attacker-controlled expected values in the comparison report.
        # A valid historical sample yielding zero rows is parser drift, not an
        # invalid artifact. Capture's initial non-vacuity gate does not apply.
        actual=_extract(clean,artifact['source_name'],artifact['source_url'],taxonomy)
        return {'status':'matched' if actual==artifact['expected'] else 'drift',
                'historical_sample':True,'sampled_only':True,'sample_count':artifact['sample_count'],
                'completeness_verified':False,'absence_reconciliation_permitted':False,
                'positive_count':len(actual['positive']),'negative_count':len(actual['explicit_negative'])}
    except Exception:
        # Operator boundary: parser exceptions may contain private source text.
        # Keep KeyboardInterrupt/SystemExit observable by excluding BaseException.
        return unavailable
