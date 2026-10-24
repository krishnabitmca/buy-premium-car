from src.source_coverage import coverage_evidence


def test_pending_pagination_is_not_complete():
    result = coverage_evidence(advertised_counts={"https://cars.example/a": 200},
        fetched_urls=["https://cars.example/a"], visited_urls={"https://cars.example/a"},
        pending_urls=["https://cars.example/b"], extracted_count=20, matched_count=10)
    assert result["coverage_status"] == "pending_traversal"
    assert result["pages_pending"] == 1
    assert result["single_scope_advertised_total"] == 200
    assert result["coverage_verified"] is False
    assert result["absence_reconciliation_permitted"] is False


def test_exhausted_frontier_does_not_authorize_sold_reconciliation():
    result = coverage_evidence(advertised_counts={"a": 200, "b": 100},
        fetched_urls=["a", "b"], visited_urls={"a", "b"},
        pending_urls=[], extracted_count=40, matched_count=40)
    assert result["coverage_status"] == "frontier_exhausted_unverified"
    assert "single_scope_advertised_total" not in result
    assert result["absence_reconciliation_permitted"] is False


def test_no_pages_and_duplicate_urls():
    result = coverage_evidence(advertised_counts={}, fetched_urls=["a", "a"],
        visited_urls=set(), pending_urls=[], extracted_count=0, matched_count=0)
    assert result["coverage_status"] == "no_pages_visited"
    assert result["pages_fetched_distinct"] == 1
