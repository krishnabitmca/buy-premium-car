from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
import math
import os
import re
from typing import Any

from .deal_engine import DealIntent, GenericDealEngine, ListingSnapshot, live_listing
from .normalize import normalize_model

def _text(v: Any) -> str:
    return str(v or "").strip()

def _num(v: Any):
    try:
        value = float(v) if v not in (None, "") else None
        return value if value is None or math.isfinite(value) else None
    except (TypeError, ValueError):
        return None

def _criterion(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _text(value).casefold())


def _rupees(value: Any):
    number = _num(value)
    return number * 100000 if number is not None else None

def car_constraints(intent: DealIntent, listing: ListingSnapshot):
    attrs={str(k).lower():v for k,v in listing.attributes.items()}
    c=attrs.get("condition")
    if intent.condition:
        if intent.condition in {"both", "used_demo"}:
            if c not in {"used", "demo"}:
                return False, "vehicle condition not verified"
        elif intent.condition != c:
            return False, f"condition does not match {intent.condition}"
    if listing.price <= 0:
        return False, "asking price not verified"
    age=_num(attrs.get("age_years"))
    if intent.min_age_years is not None:
        if age is None:return False,"vehicle age not verified"
        if age < intent.min_age_years:return False,f"vehicle is newer than your minimum age ({intent.min_age_years:g} years)"
    if intent.max_age_years is not None:
        if age is None:return False,"vehicle age not verified"
        if age > intent.max_age_years:return False,f"vehicle is older than your maximum age ({intent.max_age_years:g} years)"
    max_km=_num(attrs.get("mileage_km"))
    requested_km=intent.max_mileage_km
    if requested_km is not None:
        if max_km is None:return False,"mileage is not verified"
        if max_km > requested_km:return False,f"mileage exceeds your limit by {max_km-requested_km:,.0f} km"
    max_owners=_num(attrs.get("owner_count"))
    requested_owners=intent.max_owners
    if requested_owners is not None:
        if max_owners is None:return False,"owner count is not verified"
        if max_owners > requested_owners:return False,"owner count exceeds your limit"
    preferred=_text(intent.location)
    actual_location=_text(listing.location)
    if intent.radius_km is not None:
        distance = _num(attrs.get("distance_km"))
        if distance is None:
            return False, "distance is not verified for your radius constraint"
        if distance > intent.radius_km:
            return False, "listing exceeds your radius constraint"
    elif preferred and (not actual_location or preferred.casefold() not in actual_location.casefold()):
        return False, f"listing location does not match {preferred}"
    if intent.target_discount_pct is not None and intent.target_discount_pct > 0:
        if not listing.fair_value or listing.fair_value <= 0:
            return False, "price comparison not established for target discount"
        discount = 100 * (listing.fair_value - listing.price) / listing.fair_value
        if discount < intent.target_discount_pct:
            return False, "target discount not reached"

    return True,None

def watch_to_intent(watch: dict) -> DealIntent:
    c=watch.get("constraints") or {}
    query=_text(watch.get("natural_language_request"))
    parsed_make,parsed_model,_=normalize_model(query,query) if query else (None,None,None)
    make=c.get("make") or parsed_make
    model=c.get("model") or parsed_model
    must={}
    for key,value in (("make",make),("model",model),("fuel",c.get("fuel")),("transmission",c.get("transmission"))):
        if value:must[key]=_criterion(value)
    return DealIntent(
        intent_id=str(watch.get("watch_id") or ""),
        category="automotive",
        query=query,
        budget_min=_rupees(c.get("budget_min_lakh")),
        budget_max=_rupees(c.get("budget_max_lakh")),
        location=_text(c.get("location")) or None,
        radius_km=_num(c.get("radius_km")),
        must_have=must,
        target_discount_pct=_num(watch.get("target_discount_pct")),
        condition=_text(c.get("condition")) or None,
        min_age_years=_num(c.get("min_age_years")),
        max_age_years=_num(c.get("max_age_years")),
        max_mileage_km=_num(c.get("mileage_max_km",c.get("max_mileage_km"))),
        max_owners=_num(c.get("max_owners")),
    )

def listing_to_snapshot(v: dict, today: date | None = None) -> ListingSnapshot:
    today=today or date.today()
    mfg=_num(v.get("mfg_year") or v.get("year_manufacture"))
    age=max(0,today.year-int(mfg)) if mfg else None
    price_lakh=_num(v.get("price_lakh"))
    fair_lakh=_num(v.get("comp_median") or v.get("comparable_median_lakh"))
    tier=_num(v.get("source_tier"))
    trust={1:0.9,2:0.75,3:0.55}.get(int(tier) if tier else 3,0.5)
    condition = _text(v.get("condition_signal") or v.get("condition")).casefold()
    condition = {"demonstrator":"demo", "preowned":"used", "pre-owned":"used"}.get(condition,condition)
    attrs={
        "age_years":age,"mileage_km":v.get("km",v.get("mileage_km")),
        "owner_count":v.get("owners",v.get("owner_count")),
        "make":_criterion(v.get("brand")),"model":_criterion(v.get("model")),"fuel":_criterion(v.get("fuel")),
        "transmission":_criterion(v.get("transmission")),"condition":condition,
        "distance_km":v.get("distance_km"),
    }
    return ListingSnapshot(
        listing_id=_text(v.get("vehicle_id") or v.get("listing_id") or v.get("fingerprint") or v.get("url")),
        category="automotive",title=_text(v.get("title") or f"{v.get('brand','')} {v.get('model','')}"),
        price=(price_lakh or 0)*100000,currency="INR",source=_text(v.get("source") or v.get("source_name")),
        source_trust=trust,location=_text(v.get("location")) or None,attributes=attrs,
        fair_value=(fair_lakh*100000 if fair_lakh is not None else None),
        availability="live" if v.get("live_verified") and not v.get("sold_signal") and v.get("data_consistent",True) else "unavailable",
        observed_at=_text(v.get("observed_at") or v.get("crawled_at")),url=_text(v.get("url")),
        image_urls=tuple(v.get("image_urls") or ()),
    )

def evaluate_watch(watch: dict, vehicles: list[dict]) -> list[tuple[dict, Any]]:
    intent=watch_to_intent(watch)
    out=[]
    for vehicle in vehicles:
        snapshot=listing_to_snapshot(vehicle)
        try:
            observed = datetime.fromisoformat(snapshot.observed_at.replace("Z", "+00:00"))
            if observed.tzinfo is None:
                continue
            age = datetime.now(timezone.utc) - observed
            if age < timedelta(minutes=-5) or age > timedelta(minutes=max(60,int(os.getenv("CARSCANNER_INVENTORY_EXPIRE_MINUTES","10080")))):
                continue
        except ValueError:
            continue
        result=GenericDealEngine([live_listing, car_constraints]).evaluate(intent,snapshot)
        if result.eligible:
            quality=watch.get("alert_quality","exceptional")
            minimum={"exceptional":82.0,"good":75.0,"any":65.0}.get(quality,82.0)
            if (quality == "any" or result.match_score>=minimum) and result.confidence>=0.60:
                out.append((vehicle,result))
    return out
