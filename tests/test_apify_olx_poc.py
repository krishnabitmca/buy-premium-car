"""Fixture-only tests: never call Apify or OLX."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("apify_olx_poc", Path(__file__).resolve().parents[1] / "scripts" / "apify_olx_poc.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_summary_deduplicates_and_rejects_untrusted_rows():
    rows = [
        {"url": "https://www.olx.in/item/123", "title": "BMW X1", "price": 2000000, "images": ["https://example.com/img"]},
        {"url": "https://www.olx.in/item/123", "title": "BMW X1", "price": 2000000},
        {"url": "https://evil.example/item/999", "title": "BMW X1", "price": 100},
        {"url": "https://www.olx.in/item/456", "title": "BMW X1", "price": "2000000"},
        {},
    ]
    assert module.summarize(rows) == {"returned": 5, "valid_priced": 1, "duplicates": 1, "with_images": 1, "rejected": 3}

def test_empty_dataset():
    assert module.summarize([])["valid_priced"] == 0
