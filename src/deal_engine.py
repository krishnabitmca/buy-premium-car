from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

@dataclass(frozen=True)
class DealIntent:
    intent_id: str
    category: str
    query: str
    budget_max: Optional[float] = None
    budget_min: Optional[float] = None
    location: Optional[str] = None
    radius_km: Optional[float] = None
    must_have: dict[str, Any] = field(default_factory=dict)
    nice_to_have: dict[str, Any] = field(default_factory=dict)
    excluded: dict[str, Any] = field(default_factory=dict)
    target_discount_pct: Optional[float] = None
    condition: Optional[str] = None
    min_age_years: Optional[float] = None
    max_age_years: Optional[float] = None
    notification_channels: tuple[str, ...] = ("email",)

@dataclass(frozen=True)
class ListingSnapshot:
    listing_id: str
    category: str
    title: str
    price: float
    currency: str = "INR"
    source: str = ""
    source_trust: float = 0.5
    location: Optional[str] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    fair_value: Optional[float] = None
    availability: str = "unknown"
    observed_at: str = ""
    url: str = ""
    image_urls: tuple[str, ...] = ()

@dataclass(frozen=True)
class DealEvaluation:
    listing_id: str
    intent_id: str
    eligible: bool
    match_score: float
    deal_score: float
    confidence: float
    alert_priority: str
    reasons: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()

ConstraintFn = Callable[[DealIntent, ListingSnapshot], tuple[bool, Optional[str]]]
ValueFn = Callable[[DealIntent, ListingSnapshot], Optional[float]]

class GenericDealEngine:
    """Category-neutral matching/orchestration layer."""
    def __init__(self, hard_constraints: Iterable[ConstraintFn] = (), value_fn: Optional[ValueFn] = None, now: Optional[datetime] = None) -> None:
        self.hard_constraints = tuple(hard_constraints)
        self.value_fn = value_fn
        self.now = now or datetime.now(timezone.utc)

    def evaluate(self, intent: DealIntent, listing: ListingSnapshot) -> DealEvaluation:
        reasons, risks = [], []
        if listing.category.lower() != intent.category.lower():
            return DealEvaluation(listing.listing_id, intent.intent_id, False, 0, 0, 0, "ignore")
        for constraint in self.hard_constraints:
            ok, reason = constraint(intent, listing)
            if not ok:
                if reason: risks.append(reason)
        if intent.budget_max is not None and listing.price > intent.budget_max:
            risks.append(f"price exceeds budget by {listing.price - intent.budget_max:.2f}")
        attrs = {str(k).lower(): v for k, v in listing.attributes.items()}
        for key, desired in intent.must_have.items():
            actual = attrs.get(str(key).lower())
            matched = actual in desired if isinstance(desired, (list, tuple, set)) else actual == desired
            if not matched: risks.append(f"must-have {key} not matched")
        if risks:
            return DealEvaluation(listing.listing_id, intent.intent_id, False, 0, 0, self._confidence(listing), "ignore", (), tuple(risks))
        nice_hits = 0
        for key, desired in intent.nice_to_have.items():
            actual = attrs.get(str(key).lower())
            nice_hits += int(actual in desired if isinstance(desired, (list, tuple, set)) else actual == desired)
        fit_score = 70.0 + (15.0 if intent.must_have else 0.0)
        if intent.nice_to_have:
            fit_score += 15.0 * nice_hits / len(intent.nice_to_have)
        fair = self.value_fn(intent, listing) if self.value_fn else listing.fair_value
        deal_score = 0.0
        if fair and fair > 0 and listing.price > 0:
            gap_pct = 100.0 * (fair - listing.price) / fair
            if gap_pct > 0:
                deal_score = min(100.0, gap_pct * 4.0)
                reasons.append(f"{gap_pct:.1f}% below estimated fair value")
                if intent.target_discount_pct is not None and gap_pct >= intent.target_discount_pct:
                    reasons.append("reached your target discount")
            else:
                risks.append(f"{abs(gap_pct):.1f}% above estimated fair value")
        if listing.source_trust >= 0.8: reasons.append("high-trust source")
        elif listing.source_trust < 0.4: risks.append("lower-trust source")
        confidence = self._confidence(listing)
        match_score = round(min(100.0, 0.55 * fit_score + 0.45 * deal_score), 1)
        priority = "high" if match_score >= 80 and confidence >= 0.70 else "medium" if match_score >= 60 else "low"
        return DealEvaluation(listing.listing_id, intent.intent_id, True, match_score, round(deal_score, 1), confidence, priority, tuple(reasons), tuple(risks))

    def should_alert(self, evaluation: DealEvaluation, minimum_score: float = 75.0) -> bool:
        return evaluation.eligible and evaluation.match_score >= minimum_score and evaluation.confidence >= 0.60

    def _confidence(self, listing: ListingSnapshot) -> float:
        score = 0.45 + 0.25 * max(0.0, min(1.0, listing.source_trust))
        if listing.url: score += 0.10
        if listing.availability in {"live", "in_stock", "available"}: score += 0.10
        if listing.fair_value is not None: score += 0.10
        return round(min(1.0, score), 2)

def live_listing(intent: DealIntent, listing: ListingSnapshot) -> tuple[bool, Optional[str]]:
    if listing.availability in {"sold", "unavailable", "expired"}:
        return False, "listing is not available"
    return True, None

def location_match(intent: DealIntent, listing: ListingSnapshot) -> tuple[bool, Optional[str]]:
    return True, None
