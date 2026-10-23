"""Deterministic scraper extraction diagnostics; no network requests or invented inventory."""
from __future__ import annotations

from typing import Any


def extraction_quality(rows: list[dict[str, Any]], *, pages_fetched: int,
                       advertised_counts: dict[str, int] | None = None) -> dict[str, Any]:
    """Report observable extraction quality, not estimated marketplace recall.

    Advertised catalogue totals are directional and must not be treated as
    verified unique vehicles. Missing price/image/identity is reported rather
    than filled with fabricated values.
    """
    count = len(rows)
    with_image = sum(bool(r.get("image") or r.get("image_url")) for r in rows)
    with_price = sum(r.get("price_lakh") is not None for r in rows)
    with_identity = sum(bool(r.get("brand") and r.get("model")) for r in rows)
    with_detail_url = sum(bool(r.get("url")) for r in rows)
    advertised = {str(k): int(v) for k, v in (advertised_counts or {}).items()
                  if isinstance(v, int) and not isinstance(v, bool) and v >= 0}
    warnings = []
    if pages_fetched > 0 and count == 0:
        warnings.append("zero_listings_extracted")
    if count and with_image < count:
        warnings.append("missing_listing_images")
    if count and with_price < count:
        warnings.append("missing_listing_prices")
    if count and with_identity < count:
        warnings.append("missing_brand_or_model")
    if count and with_detail_url < count:
        warnings.append("missing_listing_links")
    if any(v > 0 for v in advertised.values()) and count == 0:
        warnings.append("advertised_inventory_not_extracted")
    return {
        "extracted_listings": count,
        "pages_fetched": pages_fetched,
        "listings_per_page": round(count / pages_fetched, 2) if pages_fetched else None,
        "with_image": with_image,
        "with_price": with_price,
        "with_brand_and_model": with_identity,
        "with_detail_url": with_detail_url,
        "advertised_counts": advertised,
        "warnings": warnings,
    }
