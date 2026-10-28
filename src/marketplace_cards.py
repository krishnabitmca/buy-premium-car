"""Source-scoped visible inventory cards, excluding navigation and EMI prices."""
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from . import live_marketplaces as lm


def _card_image_url(img, base_url):
    """Extract an HTTP(S) card image, including standard lazy-loaded srcset.

    Do not promote data placeholders, SVG icons, or script URLs to car photos.
    Preserve the existing data-src/src preference when a usable image exists.
    """
    def valid_url(value):
        if not isinstance(value,str):return None
        value=value.strip()
        if not value or value.lower().startswith(('data:','javascript:')):return None
        if value.lower().split('?',1)[0].endswith('.svg'):return None
        url=urljoin(base_url,value)
        return url if urlsplit(url).scheme in ('http','https') else None

    for attr in ('data-src','src'):
        image=valid_url(img.get(attr))
        if image:return image
    for attr in ('data-srcset','srcset'):
        srcset=img.get(attr) or ''
        # A data URI contains its own comma. Splitting first would turn the
        # base64 payload into a bogus relative photo URL (e.g. /AAAA).
        if 'data:' in srcset.lower():
            srcset=re.sub(r'data:[^,\\s]+,[^,\\s]+(?:\\s+\\d+(?:\\.\\d+)?[wx])?', '', srcset, flags=re.I)
            if 'data:' in srcset.lower():continue  # malformed data URI: fail closed
        for entry in srcset.split(','):
            parts=entry.strip().split()
            if parts:
                image=valid_url(parts[0])
                if image:return image
    return None


def parse_marketplace_cards(html, source, base_url, strategy, query=''):
    if strategy=='cartrade_cards':
        return parse_cartrade_cards(html,source,base_url,query)
    soup=BeautifulSoup(html,'html.parser')
    rows=[];seen=set()
    for anchor in soup.find_all('a',href=True):
        href=anchor['href'];path=urlsplit(href).path
        if strategy=='cardekho_cards':
            if not re.fullmatch(r'/used-car-details/[^/]+\.htm',path):continue
            card=anchor.find_parent(class_='NewUcExCard')
            if card is None:continue
            title=anchor.get('title') or anchor.get_text(' ',strip=True)
            heading=anchor.get_text(' ',strip=True)
            model_title=re.sub(r'\b(?:19|20)\d{2}\b','',heading).strip()
            location_node=card.select_one('.distanceText')
        elif strategy=='carwale_cards':
            if not re.fullmatch(r'/used/[^/]+/[^/]+/[a-z0-9]{8}/?',path,re.I):continue
            heading_node=anchor.find('h3')
            if heading_node is None:continue
            title=heading_node.get_text(' ',strip=True);model_title=re.sub(r'^(?:19|20)\d{2}\s+','',title)
            card=next((p for p in anchor.parents if any('cardFrame' in c or 'searchCardClasses' in c for c in p.get('class',[]))),None)
            if card is None:continue
            location_node=None
        elif strategy=='cars24_cards':
            if not re.fullmatch(r'/buy-used-[^/]+-\d{6,}/?',path):continue
            card=anchor
            photo=next((x for x in card.find_all('img') if re.match(r'^(?:19|20)\d{2} ',x.get('alt',''))),None)
            if photo is None:continue
            title=photo['alt'].split(' - ')[0]
            model_title=re.sub(r'^(?:19|20)\d{2}\s+','',title)
            location_node=next((x for x in card.find_all('div') if any('hubAddress' in c for c in x.get('class',[]))),None)
        else:raise ValueError('unknown marketplace card strategy')
        text=card.get_text(' ',strip=True)
        if re.search(r'\b(?:sold out|sold|no longer available)\b',text,re.I):continue
        # Require an explicitly denominated asking price; monthly EMI cannot match.
        prices=list(re.finditer(r'₹\s*([\d,]+(?:\.\d+)?)\s*(lakh|crore|cr|l)\b',text,re.I))
        year=re.search(r'\b((?:19|20)\d{2})\b',title)
        km=re.search(r'([\d,]+(?:\.\d+)?)\s*kms?\b',text,re.I)
        if not prices or not year or not km:continue
        price=prices[-1] if strategy=='cars24_cards' else prices[0]
        amount=float(price[1].replace(',',''))*(100 if price[2].lower() in {'crore','cr'} else 1)
        model_title=re.sub(r'^Mercedes\s+Benz\b','Mercedes-Benz',model_title,flags=re.I)
        brand,model=lm._infer_brand_model(model_title,None,None)
        if brand not in lm._known_brand_names() or not model or amount<=0:continue
        url=lm._canonical_url(base_url,href)
        if urlsplit(url).hostname!=urlsplit(base_url).hostname or url in seen:continue
        fuel=re.search(r'\b(Petrol|Diesel|Electric|Hybrid|CNG)\b',text,re.I)
        transmission=re.search(r'\b(Automatic|Manual|Auto)\b',text,re.I)
        location=location_node.get_text(' ',strip=True) if location_node else None
        if strategy=='carwale_cards':
            spec=anchor.find('span')
            if spec and '|' in spec.get_text():location=spec.get_text(' ',strip=True).split('|')[-1].strip()
        images=[]
        for img in card.find_all('img'):
            alt=img.get('alt','')
            if strategy=='cars24_cards' and not re.match(r'^(?:19|20)\d{2} ',alt):continue
            image=_card_image_url(img,base_url)
            if image:images.append(image)
        row={'brand':lm._canonical_brand(brand),'model':model,'variant':re.sub(r'^(?:19|20)\d{2}\s+','',title),
             'listing_name':title,'source':source,'url':url,'price_lakh':amount,'mfg_year':int(year[1]),
             'km':float(km[1].replace(',','')),'fuel':fuel[1] if fuel else None,
             'transmission':transmission[1] if transmission else None,'location':location,'seller_city':location,
             'condition_signal':'demo' if lm._infer_condition({'name':title})=='demo' else 'used','live_verified':True,'data_consistent':True,
             'images':list(dict.fromkeys(images)),'image':images[0] if images else None,
             'source_listing_id':path.rstrip('/').split('/')[-1],
             'provenance':{'source_url':base_url,'original_url':url,'extraction':strategy,'raw_listing':text}}
        if query and not lm._identity_matches_query(row,query):continue
        seen.add(url);rows.append(row)
    return rows


def parse_cartrade_cards(html,source,base_url,query=''):
    rows=[];seen=set()
    for card in BeautifulSoup(html,'html.parser').select('li.card-list-container'):
        identity=card.select_one('[data-share-make][data-share-model][data-share-mfgyear]')
        link=card.select_one('a[href] h3')
        price=card.select_one('.cr_prc')
        spec=card.select_one('[data-bhrigu-label]')
        if identity is None or link is None or price is None or spec is None:continue
        anchor=link.find_parent('a');url=lm._canonical_url(base_url,anchor['href'])
        if urlsplit(url).hostname!=urlsplit(base_url).hostname or not re.fullmatch(r'/second-hand/[^/]+/[^/]+/[a-z0-9]{8}',urlsplit(url).path,re.I):continue
        text=card.get_text(' ',strip=True)
        if re.search(r'\b(?:sold|reserved|booked)\b',text,re.I):continue
        attributes=dict(x.split('=',1) for x in spec['data-bhrigu-label'].split('|') if '=' in x)
        raw_price=price.get_text(' ',strip=True)
        amount=re.search(r'₹\s*([\d,]+(?:\.\d+)?)\s*(Lakh|Crore)?',raw_price,re.I)
        try:
            year=int(identity['data-share-mfgyear'])
            km=float(attributes['kilometers'].replace(',',''))
            value=float(amount[1].replace(',','')) if amount else 0
            unit=(amount[2] or '').lower() if amount else ''
            value=value*100 if unit=='crore' else value if unit=='lakh' else value/100000
        except (ValueError,KeyError):continue
        if value<=0 or km<0 or not 1900<=year<=2100:continue
        title=link.get_text(' ',strip=True)
        images=[x.get('src') for x in card.select('img[src]') if x.get('alt','').startswith('Used ') and not x['src'].startswith('data:')]
        row={'brand':lm._canonical_brand(identity['data-share-make']),'model':identity['data-share-model'],
            'variant':title,'listing_name':title,'url':url,'source':source,'price_lakh':value,
            'mfg_year':year,'km':km,'fuel':attributes.get('fuel'),
            'seller_city':identity.get('data-share-cityname'),'location':identity.get('data-share-cityname'),
            'condition_signal':'demo' if lm._infer_condition({'name':title})=='demo' else 'used',
            'live_verified':True,'data_consistent':True,'images':images,'image':images[0] if images else None,
            'source_listing_id':urlsplit(url).path.split('/')[-1],
            'provenance':{'source_url':base_url,'original_url':url,'extraction':'cartrade_cards','raw_listing':text}}
        if url in seen or (query and not lm._identity_matches_query(row,query)):continue
        seen.add(url);rows.append(row)
    return rows
