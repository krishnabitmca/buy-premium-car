from src.adaptive_extraction import extract_with_fallback


def test_primary_parser_wins_without_fallback():
    calls = []
    rows, trace = extract_with_fallback(
        lambda: [{"url": "https://cars.example/1"}],
        [("visible_links", lambda: calls.append("fallback") or [])],
        primary_strategy="carwale_cards",
    )
    assert len(rows) == 1
    assert calls == []
    assert trace == [{"strategy": "carwale_cards", "extracted": 1, "error": None}]


def test_empty_primary_uses_structured_fallback():
    rows, trace = extract_with_fallback(
        lambda: [], [
            ("generic_structured", lambda: [{"url": "https://cars.example/2"}]),
            ("visible_links", lambda: []),
        ], primary_strategy="cardekho_cards",
    )
    assert len(rows) == 1
    assert [x["strategy"] for x in trace] == ["cardekho_cards", "generic_structured"]


def test_no_cards_remains_unknown_not_sold():
    rows, trace = extract_with_fallback(
        lambda: [], [("visible_links", lambda: [])],
        primary_strategy="cartrade_cards",
    )
    assert rows == []
    assert all(x["extracted"] == 0 for x in trace)


def test_broken_fallback_is_recorded_without_discarding_later_fallback():
    rows, trace = extract_with_fallback(
        lambda: [], [
            ("structured", lambda: (_ for _ in ()).throw(ValueError("bad JSON"))),
            ("cards", lambda: [{"url": "https://cars.example/3"}]),
        ], primary_strategy="html_cards",
    )
    assert len(rows) == 1
    assert trace[1]["error"] == "ValueError"
    assert trace[2]["strategy"] == "cards"


def test_primary_parser_exception_not_swallowed():
    import pytest
    def bad():
        raise RuntimeError("reviewed parser broken")
    with pytest.raises(RuntimeError):
        extract_with_fallback(bad, [], primary_strategy="oem_reviewed")
