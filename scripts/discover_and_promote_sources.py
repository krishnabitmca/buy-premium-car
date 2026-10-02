from __future__ import annotations

"""Discover, validate, and promote new CarScanner source websites.

This job is intentionally separate from customer search. Search only consumes
sources that have passed a real inventory validation, so search quality does
not depend on unverified search-engine discoveries.
"""

import argparse
import time
from urllib.parse import urlparse

from src.config import load_settings
from src.discovery import discover
from src.live_marketplaces import fetch_text, parse_live_listings, parse_visible_listing_links
from src.source_intelligence import load_source_registry, normalize_condition
from src.source_registry_db import (
    enabled as source_db_enabled,
    promote_discovery,
    record_discoveries,
)


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _matches_candidate(row: dict, candidate: object) -> bool:
    brand_hint = str(getattr(candidate, "brand_hint", None) or "").strip().lower()
    condition_hint = normalize_condition(getattr(candidate, "condition", "both"))

    if brand_hint and str(row.get("brand") or "").strip().lower() != brand_hint:
        return False

    actual = normalize_condition(row.get("condition_signal"))
    if condition_hint in {"used", "demo"} and actual != condition_hint:
        return False
    return True


def validate_candidate(candidate: object) -> tuple[int, str | None]:
    url = str(getattr(candidate, "url", "") or "").strip()
    if not url:
        return 0, "missing url"

    source_name = f"Discovery validation - {_domain(url)}"
    started = time.monotonic()
    try:
        html = fetch_text(url)
        rows = parse_live_listings(html, source_name, url)
        if not rows:
            rows = parse_visible_listing_links(
                html,
                source_name,
                url,
                str(getattr(candidate, "brand_hint", "") or ""),
            )

        matching = [row for row in rows if _matches_candidate(row, candidate)]
        latency_ms = int((time.monotonic() - started) * 1000)
        if len(matching) < 2:
            return 0, f"inventory validation found {len(matching)} matching listings in {latency_ms}ms"
        return len(matching), None
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {str(exc)[:160]}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--min-confidence", type=float, default=0.70)
    args = parser.parse_args()

    if not source_db_enabled():
        raise SystemExit(
            "SOURCE_INTELLIGENCE_DATABASE_URL/DATABASE_URL is required for source promotion"
        )

    settings = load_settings(args.config)
    registry = load_source_registry(from_database=True)
    known_domains = {
        _domain(str(source.get("url") or ""))
        for source in registry
        if source.get("url")
    }

    found = discover(settings, known_domains)
    candidates = [
        item for item in found
        if float(item.candidate_confidence) >= args.min_confidence
    ][: max(0, args.max_candidates)]

    discoveries = [
        {
            "domain": item.domain,
            "url": item.url,
            "title": item.title,
            "snippet": item.snippet,
            "query": item.query,
            "source_type": item.source_type,
            "condition": item.condition,
            "segment": item.segment,
            "brand_hint": item.brand_hint or "",
            "candidate_confidence": item.candidate_confidence,
        }
        for item in candidates
    ]
    recorded = record_discoveries(discoveries)

    promoted = []
    rejected = 0
    for item in candidates:
        listings_found, error = validate_candidate(item)
        if listings_found < 2:
            rejected += 1
            print(f"REJECT domain={item.domain} reason={error}")
            continue

        name = promote_discovery(
            {
                "domain": item.domain,
                "url": item.url,
                "title": item.title,
                "query": item.query,
                "source_type": item.source_type,
                "condition": item.condition,
                "segment": item.segment,
                "brand_hint": item.brand_hint or "",
                "candidate_confidence": item.candidate_confidence,
            },
            listings_found=listings_found,
        )
        if name:
            promoted.append((name, listings_found))
            print(
                f"STAGED source={name} listings={listings_found} "
                f"brand={item.brand_hint or 'all'} condition={item.condition}"
            )

    print(
        f"discovered={len(found)} candidates={len(candidates)} "
        f"recorded={recorded} staged={len(promoted)} rejected={rejected}"
    )


if __name__ == "__main__":
    main()
