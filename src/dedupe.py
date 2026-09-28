from __future__ import annotations
from rapidfuzz.fuzz import ratio

def dedupe(vehicles):
    exact={}
    for v in vehicles: exact.setdefault(v.fingerprint,v)
    candidates=list(exact.values()); groups=[]
    for v in candidates:
        merged=False
        for e in groups:
            if not (v.brand and e.brand and v.model and e.model):continue
            if v.brand!=e.brand or v.model!=e.model:continue
            if v.year_manufacture and e.year_manufacture and abs(v.year_manufacture-e.year_manufacture)>1:continue
            if v.mileage_km and e.mileage_km and abs(v.mileage_km-e.mileage_km)>max(1000,.10*e.mileage_km):continue
            if v.price_lakh and e.price_lakh and abs(v.price_lakh-e.price_lakh)>.04*e.price_lakh:continue
            if ratio(v.title.lower(),e.title.lower())>=88:
                if v.source_tier<e.source_tier:e.source_name,e.url=v.source_name,v.url
                merged=True;break
        if not merged:groups.append(v)
    return groups
