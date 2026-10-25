from src.extraction_telemetry import summarize_extraction, summarize_committed_refresh
import pytest


def test_empty_scan_is_unknown_not_sold():
    value = summarize_extraction({"extraction_attempts": [
        {"url": "https://example.invalid/a", "extracted": 0,
         "attempts": [{"strategy": "reviewed_cards", "extracted": 0, "error": None}]}
    ]})
    assert value["pages_traced"] == 1
    assert value["pages_empty"] == 1
    assert value["records_extracted"] == 0
    assert value["absence_reconciliation_permitted"] is False


def test_fallback_recovery_and_error_counts():
    value = summarize_extraction({"extraction_attempts": [
        {"url": "https://example.invalid/a", "extracted": 2, "attempts": [
            {"strategy": "reviewed_cards", "extracted": 0, "error": None},
            {"strategy": "generic_structured", "extracted": 0, "error": "ValueError"},
            {"strategy": "visible_links", "extracted": 2, "error": None},
        ]}
    ]})
    assert value["pages_recovered_by_fallback"] == 1
    assert value["records_extracted"] == 2
    assert value["parser_errors"] == {"ValueError": 1}
    assert value["strategy_attempts"] == {
        "generic_structured": 1, "reviewed_cards": 1, "visible_links": 1,
    }


def test_missing_and_malformed_trace_does_not_claim_inventory():
    value = summarize_extraction({"extraction_attempts": [
        {"attempts": [{"strategy": "cards"}], "extracted": -10}, {"attempts": "bad"},
    ]})
    assert value["records_extracted"] == 0
    assert value["absence_reconciliation_permitted"] is False


def test_malformed_top_level_attempts_are_ignored():
    value = summarize_extraction({"extraction_attempts": {"unexpected": "object"}})
    assert value["pages_traced"] == 0
    assert value["pages_recovered_by_fallback"] == 0


def test_primary_success_is_not_mislabeled_as_fallback():
    value = summarize_extraction({"extraction_attempts": [{
        "extracted": 2, "attempts": [
            {"strategy": "primary", "extracted": 2, "error": None},
            {"strategy": "fallback", "extracted": 0, "error": None},
        ]
    }]})
    assert value["pages_recovered_by_fallback"] == 0


def test_committed_oem_inventory_is_visible_even_without_parser_page_traces():
    value = summarize_committed_refresh(
        {"extraction_attempts": []}, pages_fetched=3,
        listings_extracted=18, listings_ingested=17,
    )
    assert value["pages_traced"] == 0
    assert value["records_extracted"] == 0
    assert value["pages_fetched"] == 3
    assert value["listings_extracted"] == 18
    assert value["listings_ingested"] == 17
    assert value["absence_reconciliation_permitted"] is False


@pytest.mark.parametrize("bad_count", [-1, True, 2.5, None])
def test_committed_outcomes_reject_invalid_counts(bad_count):
    with pytest.raises(ValueError):
        summarize_committed_refresh(
            {}, pages_fetched=1, listings_extracted=2,
            listings_ingested=bad_count,
        )
