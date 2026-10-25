"""Evidence-based extraction quality gates. No source access or network activity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ExtractionAssessment:
    status: str
    reason: str
    extracted: int
    usable: int
    with_images: int


def assess_extraction(rows: list[dict[str, Any]], *, advertised: int | None = None) -> ExtractionAssessment:
    """Separate parser output from usable observations; never assert search eligibility."""
    usable = 0
    with_images = 0
    for row in rows:
        url = str(row.get("url") or "")
        parsed = urlsplit(url)
        price = row.get("price_lakh")
        valid_price = isinstance(price, (int, float)) and not isinstance(price, bool) and 0 < price < 100000
        identity = bool(row.get("brand") and row.get("model"))
        if parsed.scheme not in ("https", "http") or not parsed.hostname or not valid_price or not identity:
            continue
        usable += 1
        with_images += bool(row.get("images") or row.get("image"))
    if advertised is not None and advertised > 0 and not rows:
        status, reason = "failed", "advertised_inventory_without_cards"
    elif rows and not usable:
        status, reason = "degraded", "cards_without_usable_vehicle_evidence"
    elif rows and usable < len(rows):
        status, reason = "degraded", "partial_vehicle_evidence"
    elif not rows:
        status, reason = "unknown", "no_cards_no_authoritative_stock_evidence"
    else:
        status, reason = "parsed", "usable_observations_not_yet_customer_eligible"
    return ExtractionAssessment(status, reason, len(rows), usable, with_images)
