from __future__ import annotations
from rapidfuzz.fuzz import ratio

def _similar(a,b):
    if not (a.brand and b.brand and a.model and b.model): return False
    if a.brand!=b.brand or a.model!=b.model:return False
    if a.year_manufacture and b.year_manufacture and abs(a.year_manufacture-b.year_manufacture)>1:return False
    if a.mileage_km and b.mileage_km and abs(a.mileage_km-b.mileage_km)>max(1500,.12*a.mileage_km):return False
    if a.title and b.title and ratio(a.title.lower(),b.title.lower())<82:return False
    return True

def _merge(base,other):
    listings=list(base.source_listings or [])
    incoming=list(other.source_listings or [{"source":other.source_name,"url":other.url,"price_lakh":other.price_lakh,"location":other.location,"tier":other.source_tier}])
    seen={(x.get("source"),x.get("url")) for x in listings}
    for item in incoming:
        key=(item.get("source"),item.get("url"))
        if key not in seen:listings.append(item);seen.add(key)
    if other.source_tier<base.source_tier:
        for attr in ("source_name","source_tier","url","final_url"):
            setattr(base,attr,getattr(other,attr))
    for attr in ("location","seller_city","seller_state","registration_state","certification","condition_signal","fuel","transmission","variant","year_registration","manufacture_date","registration_date"):
        if getattr(base,attr,None) in (None,"") and getattr(other,attr,None) not in (None,""):setattr(base,attr,getattr(other,attr))
    if other.price_lakh is not None and (base.price_lakh is None or other.source_tier<base.source_tier):base.price_lakh=other.price_lakh
    if other.image_urls and not base.image_urls:base.image_urls=list(other.image_urls)
    base.source_listings=listings
    base.source_count=len(listings)
    base.lowest_observed_price_lakh=min([x["price_lakh"] for x in listings if x.get("price_lakh") is not None],default=base.price_lakh)
    base.highest_observed_price_lakh=max([x["price_lakh"] for x in listings if x.get("price_lakh") is not None],default=base.price_lakh)
    base.verification_notes=list(dict.fromkeys((base.verification_notes or [])+(other.verification_notes or [])))
    base.identity_confidence=max(base.identity_confidence,other.identity_confidence)
    return base

def dedupe(vehicles):
    exact={}
    for v in vehicles:
        if v.fingerprint in exact:
            exact[v.fingerprint]=_merge(exact[v.fingerprint],v)
        else:exact[v.fingerprint]=v
    groups=[]
    for v in exact.values():
        found=False
        for i,e in enumerate(groups):
            if _similar(v,e):
                groups[i]=_merge(e,v);found=True;break
        if not found:groups.append(v)
    return groups
