from __future__ import annotations

from datetime import date
from typing import Any

from .deal_engine import DealIntent, GenericDealEngine, ListingSnapshot, live_listing
from .normalize import normalize_model

def _text(v: Any) -> str:
    return str(v or "").strip()

def _num(v: Any):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None

def _contains(actual, desired) -> bool:
    if actual is None or desired in (None, ""):
        return True
    return _text(desired).lower() in _text(actual).lower()

def car_constraints(intent: DealIntent, listing: ListingSnapshot):
    attrs={str(k).lower():v for k,v in listing.attributes.items()}
    c=attrs.get("condition")
    if intent.condition and intent.condition not in ("used_demo",""):
        if intent.condition.lower() not in _text(c).lower() and intent.condition.lower() not in listing.title.lower():
            return False, f"condition does not match {intent.condition}"
    age=_num(attrs.get("age_years"))
    if intent.min_age_years is not None:
        if age is None:return False,"vehicle age not verified"
        if age < intent.min_age_years:return False,f"vehicle is newer than your minimum age ({intent.min_age_years:g} years)"
    if intent.max_age_years is not None:
        if age is None:return False,"vehicle age not verified"
        if age > intent.max_age_years:return False,f"vehicle is older than your maximum age ({intent.max_age_years:g} years)"
    max_km=_num(attrs.get("mileage_km"))
    requested_km=_num(attrs.get("max_mileage_km"))
    if requested_km is not None:
        if max_km is None:return False,"mileage is not verified"
        if max_km > requested_km:return False,f"mileage exceeds your limit by {max_km-requested_km:,.0f} km"
    max_owners=_num(attrs.get("owner_count"))
    requested_owners=_num(attrs.get("max_owners"))
    if requested_owners is not None:
        if max_owners is None:return False,"owner count is not verified"
        if max_owners > requested_owners:return False,"owner count exceeds your limit"
    for label,key in (("make","make"),("model","model"),("fuel","fuel"),("transmission","transmission")):
        desired=intent.must_have.get(f"intent_{key}")
        if desired and not _contains(attrs.get(key) or listing.title, desired):
            return False,f"{label} does not match"
    preferred=_text(intent.location)
    actual_location=_text(listing.location)
    if preferred and actual_location and preferred.lower() not in actual_location.lower():
        # Location is a hard constraint only when the listing exposes a conflicting
        # concrete location. Unknown location is handled as an evidence risk.
        return False,f"listing location does not match {preferred}"

    return True,None

def watch_to_intent(watch: dict) -> DealIntent:
    c=watch.get("constraints") or {}
    query=_text(watch.get("natural_language_request"))
    parsed_make,parsed_model,_=normalize_model(query,query) if query else (None,None,None)
    make=c.get("make") or parsed_make
    model=c.get("model") or parsed_model
    must={}
    for key,value in (("make",make),("model",model),("fuel",c.get("fuel")),("transmission",c.get("transmission"))):
        if value:must[f"intent_{key}"]=value
    return DealIntent(
        intent_id=str(watch.get("watch_id") or ""),
        category="automotive",
        query=query,
        budget_min=_num(c.get("budget_min_lakh")),
        budget_max=_num(c.get("budget_max_lakh")),
        location=_text(c.get("location")) or None,
        radius_km=_num(c.get("radius_km")),
        must_have=must,
        target_discount_pct=_num(watch.get("target_discount_pct")),
        condition=_text(c.get("condition")) or None,
        min_age_years=_num(c.get("min_age_years")),
        max_age_years=_num(c.get("max_age_years")),
    )

def listing_to_snapshot(v: dict, today: date | None = None) -> ListingSnapshot:
    today=today or date.today()
    mfg=_num(v.get("mfg_year") or v.get("year_manufacture"))
    age=max(0,today.year-int(mfg)) if mfg else None
    price_lakh=_num(v.get("price_lakh"))
    fair_lakh=_num(v.get("comp_median") or v.get("comparable_median_lakh"))
    tier=_num(v.get("source_tier"))
    trust={1:0.9,2:0.75,3:0.55}.get(int(tier) if tier else 3,0.5)
    condition="demo" if "demo" in (_text(v.get("title"))+" "+_text(v.get("source"))).lower() else "used"
    attrs={
        "age_years":age,"mileage_km":v.get("km") or v.get("mileage_km"),
        "owner_count":v.get("owners") or v.get("owner_count"),
        "make":v.get("brand"),"model":v.get("model"),"fuel":v.get("fuel"),
        "transmission":v.get("transmission"),"condition":condition,
    }
    return ListingSnapshot(
        listing_id=_text(v.get("fingerprint") or v.get("listing_id") or v.get("url")),
        category="automotive",title=_text(v.get("title") or f"{v.get('brand','')} {v.get('model','')}"),
        price=(price_lakh or 0)*100000,currency="INR",source=_text(v.get("source") or v.get("source_name")),
        source_trust=trust,location=_text(v.get("location")) or None,attributes=attrs,
        fair_value=(fair_lakh*100000 if fair_lakh is not None else None),
        availability="live" if v.get("live_verified") and not v.get("sold_signal") else "unavailable",
        observed_at=_text(v.get("crawled_at")),url=_text(v.get("url")),
        image_urls=tuple(v.get("image_urls") or ()),
    )

def evaluate_watch(watch: dict, vehicles: list[dict]) -> list[tuple[dict, Any]]:
    intent=watch_to_intent(watch)
    out=[]
    for vehicle in vehicles:
        snapshot=listing_to_snapshot(vehicle)
        result=GenericDealEngine([live_listing, car_constraints]).evaluate(intent,snapshot)
        if result.eligible:
            quality=watch.get("alert_quality","exceptional")
            minimum={"exceptional":82.0,"good":75.0,"any":65.0}.get(quality,82.0)
            if result.match_score>=minimum and result.confidence>=0.60:
                out.append((vehicle,result))
    return out
