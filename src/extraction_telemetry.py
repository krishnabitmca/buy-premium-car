"""Bounded, non-authoritative extraction telemetry for background scan commits.

Detailed per-page traces remain in the private scan evidence. The summary
is safe for low-cardinality metrics; it never establishes complete inventory.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_extraction(evidence: dict[str, Any] | None) -> dict[str, Any]:
    pages = (evidence or {}).get("extraction_attempts") or []
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
        fallback_pages += int(count > 0 and len(valid) > 1)
        for attempt in valid:
            strategy = attempt.get("strategy")
            if isinstance(strategy, str) and strategy:
                strategies[strategy] += 1
            error = attempt.get("error")
            if isinstance(error, str) and error:
                errors[error] += 1
    return {
        "pages_traced": len([p for p in pages if isinstance(p, dict) and p.get("attempts")]),
        "pages_empty": empty_pages,
        "pages_recovered_by_fallback": fallback_pages,
        "records_extracted": extracted,
        "strategy_attempts": dict(sorted(strategies.items())),
        "parser_errors": dict(sorted(errors.items())),
        "absence_reconciliation_permitted": False,
    }
