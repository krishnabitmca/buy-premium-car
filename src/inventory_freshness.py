from __future__ import annotations

"""Freshness classification and refresh-key helpers."""

from datetime import datetime, timezone
from typing import Any
import os


STATES = ("fresh", "aging", "stale", "expired")


def global_expiry_minutes():
    return max(60,int(os.getenv('CARSCANNER_INVENTORY_EXPIRE_MINUTES','10080')))


def expiry_minutes(condition='used', source_minutes=10080):
    global_cap=global_expiry_minutes()
    demo_cap=max(60,int(os.getenv('CARSCANNER_DEMO_EXPIRE_MINUTES','1440')))
    used_cap=max(60,int(os.getenv('CARSCANNER_USED_EXPIRE_MINUTES','2880')))
    return max(1,min(global_cap,int(source_minutes),demo_cap if condition=='demo' else used_cap))


def expiry_sql():
    # Internal aliases only; values come from bounded server configuration.
    demo_cap=max(60,int(os.getenv('CARSCANNER_DEMO_EXPIRE_MINUTES','1440')))
    used_cap=max(60,int(os.getenv('CARSCANNER_USED_EXPIRE_MINUTES','2880')))
    return f"least(%s,greatest(1,s.expire_after_minutes),case when l.condition='demo' then {demo_cap} else least(%s,{used_cap}) end)"


def freshness_state(
    last_verified_at: datetime | None,
    *,
    target_minutes: int = 360,
    stale_after_minutes: int = 1440,
    expire_after_minutes: int = 10080,
    now: datetime | None = None,
) -> str:
    if last_verified_at is None:
        return "expired"
    now = now or datetime.now(timezone.utc)
    if last_verified_at.tzinfo is None:
        last_verified_at = last_verified_at.replace(tzinfo=timezone.utc)
    age_minutes = max(0, (now - last_verified_at).total_seconds() / 60)
    if age_minutes <= target_minutes:
        return "fresh"
    if age_minutes <= stale_after_minutes:
        return "aging"
    if age_minutes <= expire_after_minutes:
        return "stale"
    return "expired"


def refresh_key(
    source_id: str,
    brand: str = "",
    model: str = "",
    condition: str = "both",
    destination_state: str = "",
) -> tuple[str, str, str, str, str]:
    return (
        str(source_id),
        str(brand or "").strip().lower(),
        str(model or "").strip().lower(),
        str(condition or "both").strip().lower(),
        str(destination_state or "").strip().lower(),
    )


def refresh_priority(
    *,
    search_count: int = 0,
    inventory_hit_count: int = 0,
    freshness: str = "fresh",
    source_reliability: float = 1.0,
) -> float:
    """Prioritize high-demand gaps and stale inventory without user identity."""
    gap = max(0, int(search_count) - int(inventory_hit_count))
    freshness_weight = {
        "fresh": 0.0,
        "aging": 1.0,
        "stale": 3.0,
        "expired": 6.0,
    }.get(freshness, 6.0)
    return round((gap + 1) * max(0.1, float(source_reliability)) * (1 + freshness_weight), 4)
