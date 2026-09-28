from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

@dataclass
class Vehicle:
    source_name: str
    source_tier: int
    url: str
    title: str
    brand: Optional[str]=None
    model: Optional[str]=None
    variant: Optional[str]=None
    year_manufacture: Optional[int]=None
    year_registration: Optional[int]=None
    manufacture_date: Optional[str]=None
    registration_date: Optional[str]=None
    mileage_km: Optional[int]=None
    owner_count: Optional[int]=None
    price_lakh: Optional[float]=None
    fuel: Optional[str]=None
    transmission: Optional[str]=None
    location: Optional[str]=None
    certification: Optional[str]=None
    condition_signal: Optional[str]=None
    image_urls: list[str]=field(default_factory=list)
    status_text: Optional[str]=None
    crawled_at: str=field(default_factory=lambda: datetime.utcnow().isoformat())
    final_url: Optional[str]=None
    http_status: Optional[int]=None
    live_verified: bool=False
    sold_signal: bool=False
    data_consistent: bool=True
    duplicate_key: Optional[str]=None
    fingerprint: Optional[str]=None
    price_delta_pct: Optional[float]=None
    comparable_count: int=0
    comparable_median_lakh: Optional[float]=None
    comparable_low_lakh: Optional[float]=None
    comparable_high_lakh: Optional[float]=None
    discount_vs_comparable_pct: Optional[float]=None
    km_per_year: Optional[float]=None
    opportunity_score: Optional[float]=None
    opportunity_class: Optional[str]=None
    verification_notes: list[str]=field(default_factory=list)
    def to_dict(self):return asdict(self)
