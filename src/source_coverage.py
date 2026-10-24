"""Conservative source coverage evidence.

Advertised counts can refer to overlapping pages or unrelated scopes. Never
sum them or infer absence authority from a page count.
"""
from __future__ import annotations


def coverage_evidence(*, advertised_counts, fetched_urls, visited_urls,
                      pending_urls, extracted_count, matched_count):
    totals = [v for v in advertised_counts.values()
              if type(v) is int and v >= 0]
    distinct = len(set(fetched_urls))
    pending = len(set(pending_urls) - set(visited_urls))
    evidence = {
        "pages_fetched_distinct": distinct,
        "pages_visited_in_generation": len(set(visited_urls)),
        "pages_pending": pending,
        "advertised_scope_count": len(totals),
        "advertised_totals_by_url": dict(advertised_counts),
        "extracted_unique_in_batch": extracted_count,
        "matched_in_batch": matched_count,
        "coverage_verified": False,
        "absence_reconciliation_permitted": False,
    }
    # A single scope's total is useful for diagnosis but cannot be compared
    # with a batch that may contain other scopes or previous continuation pages.
    if len(totals) == 1:
        evidence["single_scope_advertised_total"] = totals[0]
    evidence["coverage_status"] = (
        "pending_traversal" if pending else
        "frontier_exhausted_unverified" if visited_urls else "no_pages_visited"
    )
    return evidence
