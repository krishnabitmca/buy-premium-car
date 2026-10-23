from src.scraper_quality import extraction_quality


def test_complete_scraper_rows_report_no_warnings():
    rows = [{"brand": "BMW", "model": "X5", "price_lakh": 45,
             "url": "https://example.test/car/1", "image": "https://example.test/1.jpg"}]
    report = extraction_quality(rows, pages_fetched=2)
    assert report["extracted_listings"] == 1
    assert report["listings_per_page"] == 0.5
    assert report["warnings"] == []


def test_missing_fields_are_flagged_without_inventing_inventory():
    rows = [{"brand": "BMW", "model": "", "price_lakh": None, "url": "", "image": ""}]
    report = extraction_quality(rows, pages_fetched=1)
    assert set(report["warnings"]) == {
        "missing_listing_images", "missing_listing_prices",
        "missing_brand_or_model", "missing_listing_links"}
    assert report["with_image"] == 0
    assert report["with_price"] == 0


def test_advertised_inventory_zero_extraction_is_visible():
    report = extraction_quality([], pages_fetched=3,
                                advertised_counts={"https://example.test": 1000})
    assert "advertised_inventory_not_extracted" in report["warnings"]
    assert "zero_listings_extracted" in report["warnings"]
    assert report["extracted_listings"] == 0


def test_no_pages_does_not_divide_by_zero_or_guess_recall():
    report = extraction_quality([], pages_fetched=0)
    assert report["listings_per_page"] is None
    assert report["warnings"] == []
