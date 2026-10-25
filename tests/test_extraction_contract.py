from src.extraction_contract import assess_extraction


def test_advertised_empty_is_failure_not_zero_stock():
    assert assess_extraction([], advertised=20).status == "failed"


def test_empty_without_advertisement_is_unknown():
    assert assess_extraction([]).status == "unknown"


def test_parser_only_rows_not_counted_as_usable():
    result = assess_extraction([{"brand": "BMW", "model": "X1", "url": "https://example.com/car"}])
    assert (result.status, result.usable) == ("degraded", 0)


def test_usable_observation_is_not_customer_eligibility():
    row = {"brand": "BMW", "model": "X1", "url": "https://example.com/car",
           "price_lakh": 32.5, "images": ["https://example.com/car.jpg"]}
    result = assess_extraction([row])
    assert (result.status, result.usable, result.with_images) == ("parsed", 1, 1)


def test_non_http_and_boolean_price_rejected():
    rows = [{"brand": "BMW", "model": "X1", "url": "javascript:alert(1)", "price_lakh": 12},
            {"brand": "BMW", "model": "X1", "url": "https://example.com/x", "price_lakh": True}]
    assert assess_extraction(rows).usable == 0
