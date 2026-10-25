from src.extraction_telemetry import summarize_extraction


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
