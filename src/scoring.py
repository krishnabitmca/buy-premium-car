from __future__ import annotations
from statistics import median

def age_years(v,ref_date):
    if not v.year_manufacture:return None
    return max(0,int(ref_date[:4])-v.year_manufacture)

def enrich_and_score(v,comparable_rows,settings):
    ref=settings.market["reference_date"]; a=age_years(v,ref)
    if v.mileage_km and a and a>0:v.km_per_year=v.mileage_km/a
    vals=[r["price_lakh"] for r in comparable_rows if r["price_lakh"]]
    v.comparable_count=len(vals)
    if vals:
        v.comparable_median_lakh=median(vals);v.comparable_low_lakh=min(vals);v.comparable_high_lakh=max(vals)
        if v.price_lakh:v.discount_vs_comparable_pct=100*(v.comparable_median_lakh-v.price_lakh)/v.comparable_median_lakh
    score=min(30,max(0,(v.discount_vs_comparable_pct or 0)*2))
    if v.owner_count==1:score+=12
    if v.mileage_km is not None:score+=12 if v.mileage_km<=settings.market["low_mileage_km"] else (6 if v.mileage_km<=settings.market["mileage_preference_km"] else 0)
    if v.km_per_year is not None and v.km_per_year<=9000:score+=10
    if v.source_tier==1:score+=8
    if v.certification or v.condition_signal:score+=5
    if v.live_verified:score+=8
    if v.data_consistent:score+=5
    if v.sold_signal:
        v.opportunity_score=0
        v.opportunity_class="watch"
        return v
    v.opportunity_score=round(min(100,score),1)
    d=v.discount_vs_comparable_pct or 0
    if v.live_verified and v.data_consistent and d>=settings.market["exceptional_discount_vs_comparables_pct"] and v.comparable_count>=settings.market["min_comparables_for_price_call"]:v.opportunity_class="exceptional"
    elif v.live_verified and v.data_consistent and d>=settings.market["bargain_discount_vs_comparables_pct"] and v.comparable_count>=settings.market["min_comparables_for_price_call"]:v.opportunity_class="bargain"
    elif v.live_verified and v.data_consistent and v.mileage_km is not None and v.mileage_km<=settings.market["low_mileage_km"]:v.opportunity_class="low-mileage-watch"
    else:v.opportunity_class="watch"
    return v

def negotiation_band(v):
    if not v.price_lakh:return None,None
    factor={"exceptional":(.90,.95),"bargain":(.93,.97),"low-mileage-watch":(.95,.98)}.get(v.opportunity_class,(.96,.99))
    return round(v.price_lakh*factor[0],2),round(v.price_lakh*factor[1],2)
