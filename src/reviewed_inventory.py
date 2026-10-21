"""Reviewed public dealer/OEM stock. No leads, account APIs or inferred demos."""
import http.cookiejar
import hashlib
import json
import math
import re
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup

from . import live_marketplaces as lm
from .dealer_inventory import _price, _text


def _brand(label):
    tokens=lm._identity_tokens(label)
    for alias,canonical in lm.BRAND_ALIASES.items():
        if lm._identity_tokens(alias)==tokens:
            tokens=lm._identity_tokens(canonical);break
    for name in lm._known_brand_names():
        if lm._identity_tokens(name)==tokens:return name
    if tokens==['range','rover','land','rover']:return 'Land Rover'
    return None


def _listing_url(base,href,pattern):
    url=urllib.parse.urljoin(base,href or '')
    parts=urllib.parse.urlsplit(url)
    if parts.scheme not in {'http','https'} or parts.hostname!=urllib.parse.urlsplit(base).hostname:return None
    return url if re.fullmatch(pattern,parts.path) and not parts.query and not parts.fragment else None


def _fusion_model(brand,label,title):
    clean=re.sub(r'^(?:19|20)\d{2}(?:/(?:\d{2,4}|UNREGISTERED))?\s+','',title,flags=re.I)
    model=re.sub(r'^'+re.escape(label)+r'\s+','',clean,flags=re.I)
    if model==clean and brand:model=re.sub(r'^'+re.escape(brand)+r'\s+','',clean,flags=re.I)
    if brand=='Mercedes-Benz':
        model=re.sub(r'^MERCEDES\s+','',model,flags=re.I)
        family=re.fullmatch(r'([ACEGS])\s*\d{3}.*',model,re.I)
        if family:model=family[1].upper()+'-Class'
    if brand=='BMW' and re.match(r'^[357]\d{2}',model):model=model[0]+' Series'
    return model


def parse_reviewed_cards(html,source,base,strategy,query=''):
    soup=BeautifulSoup(html,'html.parser');rows={}
    cards=soup.select('.product[data-price][data-features]') if strategy=='fusion_cards' else soup.select('a.carousel__card[href]')
    for card in cards:
        if re.search(r'\b(sold(?: out)?|booked|reserved|no longer available)\b',_text(card),re.I):continue
        if strategy=='fusion_cards':
            anchor=card.select_one('a[href]');title=_text(card.select_one('.car_heading h5'))
            url=_listing_url(base,anchor.get('href') if anchor else None,r'/cars/[^/]+/?')
            price=_price(_text(card.select_one('.car-price')))
            brand_label=card.get('data-features','');brand=_brand(brand_label)
            model=_fusion_model(brand,brand_label,title)
            fields={_text(li.select_one('h6')).lower():_text(li.select_one('.asert')) for li in card.select('.car_info li')}
            mileage=fields.get('kms','');year=fields.get('registered','')
            fuel=fields.get('fuel');location=None
            stock_id=url.rstrip('/').rsplit('/',1)[-1] if url else None
            specs={}
        else:
            title=_text(card.select_one('.carousel__variant'))
            brand=_brand(_text(card.select_one('.carousel__make')))
            url=_listing_url(base,card.get('href'),r'/car-details/\d+/?')
            price=_price(_text(card.select_one('.carousel__price')))
            variant=card.select_one('.carousel__variant')
            model=' '.join(t.strip() for t in variant.find_all(string=True,recursive=False)) if variant else ''
            model=re.sub(r'\((?:19|20)\d{2}-(?:19|20)\d{2}\)','',model).strip()
            specs={}
            for li in card.select('.carousel__spec-item'):
                icon=li.select_one('i');classes=icon.get('class',[]) if icon else []
                for name in classes:specs[name]=_text(li.select_one('.carousel__spec-label'))
            mileage=specs.get('icon-meter','').removesuffix('kms').strip();year=''
            fuel=specs.get('icon-sag-station');location=_text(card.select_one('.carousel__loc-label')) or None
            stock_id=url.rstrip('/').rsplit('/',1)[-1] if url else None
        if not (url and price and brand and model and title):continue
        image=card.select_one('img[src]')
        km=float(mileage.replace(',','')) if re.fullmatch(r'[\d,]+',mileage) else None
        owner=re.search(r'^(\d+)',specs.get('icon-owner',''))
        row=dict(source=source,source_listing_id=stock_id,brand=brand,model=model,
            listing_name=title if strategy=='fusion_cards' else brand+' '+title,variant=title,
            url=url,price_lakh=price,km=km,registration_year=int(year) if re.fullmatch(r'(?:19|20)\d{2}',year) else None,
            mfg_year=None,owners=int(owner[1]) if owner else None,
            fuel=fuel,transmission=specs.get('icon-transmission'),location=location,
            images=[urllib.parse.urljoin(base,image['src'])] if image and not image['src'].startswith('data:') else [],
            condition_signal='used',live_verified=True,data_consistent=True,
            provenance=dict(source_url=base,original_url=url,extraction=strategy,
                condition_evidence='Individual stock card on the source used-car catalogue; no demonstrator inference'))
        if not query or lm._identity_matches_query(row,query):rows[url]=row
    return list(rows.values())


def parse_autohangar_cards(html,source,base,query=''):
    """Parse the public AutoHangar catalogue without treating lead forms as offers.

    AutoHangar currently exposes one catalogue URL rather than per-vehicle links.
    A stable source-local key keeps the independently priced cards distinct while
    the buyer handoff remains the original public catalogue.
    """
    if urllib.parse.urlsplit(base).hostname not in {'autohangar.net','www.autohangar.net'}:
        raise ValueError('Unreviewed AutoHangar host')
    soup=BeautifulSoup(html,'html.parser');rows={}
    cards=soup.select('.cars-box')
    for card in cards:
        text=_text(card)
        sold=bool(re.search(r'\b(sold(?: out)?|booked|reserved|no longer available)\b',text,re.I))
        title=_text(card.select_one('.carName'))
        try:
            price=_price(_text(card.select_one('.carPrice')))
        except (OverflowError,ValueError):
            price=None
        if price is not None and (not math.isfinite(price) or not 0 < price <= 2000):
            price=None
        year=_text(card.select_one('.carYear'))
        details=_text(card.select_one('.carDetails'))
        if re.match(r'^Range Rover\b',title,re.I):
            brand,model='Land Rover',title
        else:
            brand,model=lm._infer_brand_model(title,None,None)
        brand=lm._canonical_brand(brand or '')
        known={lm._canonical_brand(name).lower() for name in lm._known_brand_names()}
        if brand.lower() not in known:
            brand=model=''
        elif brand and model:
            model=_fusion_model(brand,brand,title)
        if not (title and re.fullmatch(r'(?:19|20)\d{2}',year)):
            continue
        mileage=re.search(r'([\d,]+)\s*Kms?\b',details,re.I)
        mileage_value=mileage[1].replace(',','') if mileage else ''
        if not re.fullmatch(r'\d{1,9}',mileage_value):
            mileage=None;mileage_value=''
        fuel=next((name for name in ('Petrol','Diesel','CNG','Electric','Hybrid')
                   if re.search(r'\b'+re.escape(name)+r'\b',details,re.I)),None)
        image=card.select_one('img[src]')
        # The catalogue exposes no durable stock ID or detail URL. Keep the
        # identity conservative and stable across price, mileage and photo
        # updates. Same-title/year collisions collapse rather than inventing
        # distinct physical cars from mutable presentation fields.
        fingerprint='|'.join((title.lower(),year))
        stock_id='catalogue-'+hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
        if sold:
            row=dict(source=source,source_listing_id=stock_id,listing_name=title,
                brand=brand or None,model=model or None,url=base,price_lakh=price,
                condition_signal='used',live_verified=False,sold_signal=True,
                data_consistent=True,images=[],
                metadata={'source_year':int(year),'source_year_semantics':'unclassified',
                          'provenance':{'source_url':base,'original_url':base,
                              'extraction':'autohangar_cards','offer_identity':'source catalogue card',
                              'availability_evidence':'Explicit sold/booked/reserved text on the matching catalogue card'}},
                provenance=dict(source_url=base,original_url=base,extraction='autohangar_cards',
                    offer_identity='source catalogue card',
                    availability_evidence='Explicit sold/booked/reserved text on the matching catalogue card'))
            if not query or lm._identity_matches_query(row,query):
                rows[stock_id]=row
            continue
        if not (price and brand and model):
            continue
        image_url=urllib.parse.urljoin(base,image['src']) if image and image.get('src') else ''
        image_parts=urllib.parse.urlsplit(image_url)
        base_host=urllib.parse.urlsplit(base).hostname
        safe_images=[image_url] if image_parts.scheme in {'http','https'} and image_parts.hostname==base_host else []
        row=dict(source=source,source_listing_id=stock_id,brand=brand,model=model,
            listing_name=title,variant=model,url=base,price_lakh=price,
            km=float(mileage_value) if mileage else None,
            registration_year=None,
            mfg_year=None,owners=None,fuel=fuel,transmission=None,location=None,
            images=safe_images,
            metadata={'source_year':int(year),'source_year_semantics':'unclassified',
                      'provenance':{'source_url':base,'original_url':base,
                          'extraction':'autohangar_cards','offer_identity':'source catalogue card',
                          'condition_evidence':'Card published in the source pre-owned luxury-car catalogue'}},
            condition_signal='used',live_verified=True,data_consistent=True,
            provenance=dict(source_url=base,original_url=base,extraction='autohangar_cards',
                offer_identity='source catalogue card',
                condition_evidence='Card published in the source pre-owned luxury-car catalogue'))
        if not query or lm._identity_matches_query(row,query):
            rows[stock_id]=row
    if cards and not rows:
        raise ValueError('AutoHangar catalogue cards yielded no valid evidence')
    return list(rows.values())


def reviewed_detail_evidence(html,url,brand,model,condition='used'):
    """Renew only an identified individual page, never related cars or EMI."""
    soup=BeautifulSoup(html,'html.parser');parts=urllib.parse.urlsplit(url)
    if parts.hostname=='fusioncars.in' and re.fullmatch(r'/cars/[^/]+/?',parts.path):
        canonical=soup.select_one('link[rel="canonical"][href]')
        if not canonical or canonical['href'].rstrip('/')!=url.rstrip('/'):return {'outcome':'inconclusive'}
        scope=soup.select_one('section.fusion_single')
        title=_text(scope.select_one('.car_single_heading')) if scope else ''
        price=_price(_text(scope.select_one('.car_single_price'))) if scope else None
        family=_fusion_model(brand,brand.replace('-',' '),title)
        identity={'listing_name':title,'model':family}
        unavailable=False
        for badge in soup.select('.my-badge'):
            anchor=badge.find_parent('a',href=True)
            identifies_target=anchor and _listing_url(url,anchor['href'],r'/cars/[^/]+/?')==url
            if (badge.find_parent('section',class_='fusion_single') or identifies_target) and re.search(r'\b(sold|booked|reserved)\b',_text(badge),re.I):
                unavailable=True
    elif parts.hostname=='www.skodapreowned.in' and re.fullmatch(r'/car-details/\d+/?',parts.path):
        scope=soup.select_one('.car-wraper');stock_id=parts.path.rstrip('/').rsplit('/',1)[-1]
        if not scope or not any('/dms-stock-images/'+stock_id+'/' in image.get('src','') for image in scope.select('img[src]')):
            return {'outcome':'inconclusive'}
        title=_text(scope.select_one('.card-body'))
        identity={'listing_name':title}
        price=_price(_text(scope.select_one('h4')))
        unavailable=False
    else:return {'outcome':'inconclusive'}
    if not lm._identity_matches_query(identity,brand+' '+model):return {'outcome':'inconclusive'}
    if unavailable or re.search(r'\b(sold(?: out)?|booked|reserved|no longer available)\b',_text(scope),re.I):
        return {'outcome':'unavailable','availability':'source_explicit_unavailable'}
    if condition=='demo':return {'outcome':'condition_unverified'}
    if not price:return {'outcome':'inconclusive'}
    return {'outcome':'available','price_lakh':price,'availability':'priced_individual_used_stock_page'}


def fetch_skoda_inventory(url,source,*,continuation=None,page_budget=3,opener=None):
    """Mirror buy.js's public read-only stock POST; cookies/CSRF stay in memory."""
    from .oem_inventory import OEMInventoryBatch
    from .listing_evidence import SameOriginRedirect
    if url!='https://www.skodapreowned.in/buy':raise ValueError('Unreviewed Skoda stock endpoint')
    opener=opener or urllib.request.build_opener(SameOriginRedirect(),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def read(request):
        with opener.open(request,timeout=15) as response:
            raw=response.read(lm.MAX_BODY_BYTES+1)
            if len(raw)>lm.MAX_BODY_BYTES:raise ValueError('OEM response exceeded limit')
            return raw.decode('utf-8','replace')
    headers={'User-Agent':lm.USER_AGENT,'Referer':url}
    bootstrap=read(urllib.request.Request(url,headers=headers))
    token=re.search(r'\btoken:\s*[\'"]([^\'"]+)',bootstrap)
    endpoint=re.search(r'\bbuySearch:\s*[\'"]([^\'"]+)',bootstrap)
    if not token or not endpoint or endpoint[1]!='https://www.skodapreowned.in/buySearch':
        raise ValueError('OEM public stock contract changed')
    page=int((continuation or {}).get('next_page',1))
    if not 1<=page<=10000:raise ValueError('Invalid OEM stock position')
    rows=[];pages=0;pending=None
    while pages<max(1,min(int(page_budget),50)):
        # Read every inventory page through the same public API. The initial
        # server-rendered cards can have a different order from buy.js results.
        fields={key:'' for key in ('sort_by','search_city','search_vehicle_type','search_year','search_make',
            'search_model','price_checkbox','search_make_icon','km_range','certified','search_fuel','transmission_type','search_no_owner')}
        fields.update(_token=token[1],move_page=page,per_page=6)
        payload=read(urllib.request.Request(endpoint[1],data=urllib.parse.urlencode(fields).encode(),
            headers={**headers,'X-Requested-With':'XMLHttpRequest'}))
        data=json.loads(payload)
        if not isinstance(data,dict) or not isinstance(data.get('stock'),str):raise ValueError('Unexpected OEM stock response')
        body=data['stock']
        soup=BeautifulSoup(body,'html.parser')
        current=soup.select_one('.pagination .active .page_move[data-page]')
        if not current or current.get('data-page')!=str(page):raise ValueError('OEM pagination stalled or metadata disappeared')
        parsed=parse_reviewed_cards(body,source,url,'skoda_cards')
        if not parsed:raise ValueError('OEM advertised page yielded no valid stock')
        rows.extend(parsed);pages+=1
        advertised={int(a['data-page']) for a in soup.select('.page_move[data-page]') if a['data-page'].isdigit()}
        if page+1 not in advertised:
            pending=None;break
        page+=1;pending={'next_page':page}
    return OEMInventoryBatch(list({r['url']:r for r in rows}.values()),pending,pages)
