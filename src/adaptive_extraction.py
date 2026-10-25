"""Conservative, observable parser fallback for fetched catalogue HTML.

Strategy-specific parsers remain authoritative. A fallback may recover genuine
cards, but an empty result never implies inventory is sold out.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ExtractionAttempt:
    strategy: str
    extracted: int
    error: str | None = None


def extract_with_fallback(
    primary: Callable[[], list[dict[str, Any]]],
    fallbacks: list[tuple[str, Callable[[], list[dict[str, Any]]]]],
    *,
    primary_strategy: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Try alternatives only after an empty primary result.

    Do not hide a primary exception: a failed reviewed parser signals a real
    source failure rather than permission to silently claim a healthy scan.
    """
    rows = primary()
    attempts = [ExtractionAttempt(primary_strategy, len(rows))]
    if rows:
        return rows, [a.__dict__ for a in attempts]
    for name, extractor in fallbacks:
        try:
            candidates = extractor()
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            attempts.append(ExtractionAttempt(name, 0, type(exc).__name__))
            continue
        attempts.append(ExtractionAttempt(name, len(candidates)))
        if candidates:
            return candidates, [a.__dict__ for a in attempts]
    return [], [a.__dict__ for a in attempts]
