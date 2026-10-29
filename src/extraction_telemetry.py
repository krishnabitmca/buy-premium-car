"""Bounded, non-authoritative extraction telemetry for background scan commits.

Detailed per-page traces remain in the private scan evidence. The summary
is safe for low-cardinality metrics; it never establishes complete inventory.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_extraction(evidence: dict[str, Any] | None) -> dict[str, Any]:
    pages = (evidence or {}).get("extraction_attempts") or []
    if not isinstance(pages, list):
        pages = []
    strategies: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    empty_pages = fallback_pages = 0
    extracted = 0
    for page in pages:
        if not isinstance(page, dict):
            continue
        attempts = page.get("attempts") or []
        if not isinstance(attempts, list):
            continue
        valid = [attempt for attempt in attempts if isinstance(attempt, dict)]
        if not valid:
            continue
        count = page.get("extracted", 0)
        if type(count) is not int or count < 0:
            count = 0
        extracted += count
        empty_pages += int(count == 0)
        # More than one attempt does not prove a fallback recovered data;
        # a prior strategy may already have extracted records.
        fallback_pages += int(count > 0 and len(valid) > 1
                              and not any(type(a.get("extracted")) is int
                                          and a["extracted"] > 0 for a in valid[:-1])
                              and type(valid[-1].get("extracted")) is int
                              and valid[-1]["extracted"] > 0)
        for attempt in valid:
            strategy = attempt.get("strategy")
            if isinstance(strategy, str) and strategy:
                strategies[strategy] += 1
            error = attempt.get("error")
            if isinstance(error, str) and error:
                errors[error] += 1
    # Explicit allowlist prevents arbitrary scraper metadata, URLs, or seller
    # information from leaking into low-cardinality production logs.
    allowed_rejections = (
        'tombstone', 'identity', 'demo_evidence', 'used_excludes_demo',
        'below_min_or_missing_price', 'above_max_or_missing_price',
    )
    quality = (evidence or {}).get('scraper_quality') or {}
    if not isinstance(quality, dict):
        quality = {}
    raw_rejections = quality.get('filter_rejection_counts') or {}
    if not isinstance(raw_rejections, dict):
        raw_rejections = {}
    # A bounded decimal width is important even for malformed private evidence.
    max_count = 1_000_000_000
    rejections = {key: raw_rejections[key] for key in allowed_rejections
                  if type(raw_rejections.get(key)) is int and 0 <= raw_rejections[key] <= max_count}
    raw_dedup = quality.get('deduplicated_within_source_count')
    deduplicated = (raw_dedup if type(raw_dedup) is int and 0 <= raw_dedup <= max_count else 0)
    return {
        'filter_rejection_counts': rejections,
        'deduplicated_within_source_count': deduplicated,
        "pages_traced": sum(1 for p in pages if isinstance(p, dict)
                            and isinstance(p.get("attempts"), list)
                            and any(isinstance(a, dict) for a in p["attempts"])),
        "pages_empty": empty_pages,
        "pages_recovered_by_fallback": fallback_pages,
        "records_extracted": extracted,
        "strategy_attempts": dict(sorted(strategies.items())),
        "parser_errors": dict(sorted(errors.items())),
        "absence_reconciliation_permitted": False,
    }


def summarize_committed_refresh(
    evidence: dict[str, Any] | None, *, pages_fetched: int,
    listings_extracted: int, listings_ingested: int,
) -> dict[str, Any]:
    """Combine per-page parser traces with durable per-job outcome counters.

    Specialized OEM parsers do not always emit per-page strategy traces.
    Consequently zero traced records must never be presented as zero inventory.
    This function is called only after the database transaction commits.
    """
    counts = {
        "pages_fetched": pages_fetched,
        "listings_extracted": listings_extracted,
        "listings_ingested": listings_ingested,
    }
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("Committed refresh counts must be nonnegative integers")
    return {**summarize_extraction(evidence), **counts}
