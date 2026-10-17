"""Strict per-listing evidence. Page-wide prices/FAQ text never renew inventory."""
import json
import math
import re
import urllib.request
from urllib.parse import urlsplit,urljoin
from bs4 import BeautifulSoup
from .live_marketplaces import _canonical_url,_identity_matches_query,USER_AGENT,MAX_BODY_BYTES


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlsplit(newurl).hostname!=urlsplit(req.full_url).hostname or (
                urlsplit(req.full_url).scheme=='https' and urlsplit(newurl).scheme!='https'):
            raise ValueError('Listing redirected outside its approved origin')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch_listing(url):
    request=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'text/html,application/ld+json'})
    with urllib.request.build_opener(SameOriginRedirect()).open(request,timeout=10) as response:
        raw=response.read(MAX_BODY_BYTES+1)
        if len(raw)>MAX_BODY_BYTES:raise ValueError('Listing response exceeded limit')
        if not any(t in response.headers.get('Content-Type','').lower() for t in ('text/html','application/ld+json')):
            raise ValueError('Unsupported listing response')
        if _canonical_url(url,response.url)!=_canonical_url(url,url):
            raise ValueError('Listing redirected to a different page')
        return raw.decode(response.headers.get_content_charset() or 'utf-8','replace')


def structured_evidence(html,url,brand,model):
    target=_canonical_url(url,url)
    candidates=[]
    def walk(value):
        if isinstance(value,list):
            for item in value:yield from walk(item)
        elif isinstance(value,dict):
            yield value
            for item in value.values():yield from walk(item)
    for script in BeautifulSoup(html,'html.parser').select('script[type="application/ld+json"]'):
        try:root=json.loads(script.string or script.get_text())
        except (ValueError,TypeError):continue
        for product in walk(root):
            types=product.get('@type',[])
            if isinstance(types,str):types=[types]
            if not set(types)&{'Product','Vehicle','Car'}:continue
            product_url=product.get('url') or product.get('@id')
            if not isinstance(product_url,str) or _canonical_url(url,urljoin(url,product_url))!=target:continue
            name=product.get('name')
            if not isinstance(name,str) or not _identity_matches_query({'brand':name,'model':name,'listing_name':name},brand+' '+model):continue
            offers=product.get('offers',[])
            if isinstance(offers,dict):offers=[offers]
            if not isinstance(offers,list):continue
            for offer in offers:
                if not isinstance(offer,dict) or offer.get('@type')=='AggregateOffer':continue
                offer_url=offer.get('url')
                if offer_url and (not isinstance(offer_url,str) or _canonical_url(url,urljoin(url,offer_url))!=target):continue
                availability=str(offer.get('availability','')).rsplit('/',1)[-1]
                if availability in {'SoldOut','OutOfStock','Discontinued'}:
                    candidates.append({'outcome':'unavailable','availability':availability})
                elif availability in {'InStock','LimitedAvailability'} and offer.get('priceCurrency')=='INR':
                    try:price=float(str(offer['price']).replace(',',''))/100000
                    except (ValueError,TypeError,KeyError):continue
                    if math.isfinite(price) and price>0:
                        candidates.append({'outcome':'available','price_lakh':price,'availability':availability})
    # Conflicting products/offers must not silently choose the cheapest claim.
    unique={json.dumps(row,sort_keys=True):row for row in candidates}
    return next(iter(unique.values())) if len(unique)==1 else {'outcome':'inconclusive'}


def catalogue_tombstones(html,base_url,strategy):
    selectors={
        'luxuryride_cards':('.tfcl-listing-card, .listing-post',r'/listing/[^/]+/?'),
        'cartrade_cards':('li.card-list-container',r'/second-hand/[^/]+/[^/]+/[a-z0-9]{8}/?'),
        'cardekho_cards':('.NewUcExCard',r'/used-car-details/[^/]+\.htm'),
        'carwale_cards':('[class*="cardFrame"], [class*="searchCardClasses"]',r'/used/[^/]+/[^/]+/[a-z0-9]{8}/?'),
    }
    if strategy not in selectors:return []
    selector,path_pattern=selectors[strategy];found={}
    for card in BeautifulSoup(html,'html.parser').select(selector):
        marker=re.search(r'\b(sold(?: out)?|booked|reserved|no longer available)\b',card.get_text(' ',strip=True),re.I)
        if not marker:continue
        for anchor in card.select('a[href]'):
            url=_canonical_url(base_url,anchor['href'])
            if urlsplit(url).hostname!=urlsplit(base_url).hostname or not re.fullmatch(path_pattern,urlsplit(url).path,re.I):continue
            found[url]={'url':url,'reason':marker[0].lower(),'evidence_url':base_url}
    return list(found.values())
