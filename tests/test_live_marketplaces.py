from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import live_marketplaces as lm

FIXTURE = """
<html><script type="application/ld+json">
{
  "@type": "Product",
  "name": "BMW X5 xDrive40i",
  "brand": {"@type": "Brand", "name": "BMW"},
  "model": "X5",
  "vehicleConfiguration": "xDrive40i M Sport",
  "offers": {"price": "4950000", "url": "/used/bmw-x5"},
  "url": "/used/bmw-x5"
}
</script></html>
"""

rows = lm.parse_live_listings(FIXTURE, "Fixture", "https://example.com/")
assert len(rows) == 1, rows
row = rows[0]
assert row["brand"] == "BMW"
assert row["model"] == "X5"
assert row["price_lakh"] == 49.5
assert row["live_verified"] is True
assert row["url"] == "https://example.com/used/bmw-x5"

print("PASS: live listing parser")


def test_paginated_source_follows_canonical_next_pages(monkeypatch):
    from src import live_marketplaces as lm
    pages = {
        "https://example.com/cars": '<a rel="next" href="/cars?page=2">Next</a>',
        "https://example.com/cars?page=2": '<a rel="next" href="/cars?page=3">Next</a>',
        "https://example.com/cars?page=3": '<html>end</html>',
    }
    calls = []
    monkeypatch.setattr(lm, "fetch_text", lambda url: calls.append(url) or pages[url])
    monkeypatch.setattr(lm, "parse_live_listings", lambda html, source, url: [{"brand":"BMW","model":url.split("page=")[-1] if "page=" in url else "1","url":url,"price_lakh":50,"condition_signal":"used"}])
    rows, crawled = lm._crawl_paginated_source("https://example.com/cars", "Example", "", "both", max_pages=5)
    assert len(rows) == 3
    assert len(crawled) == 3
    assert calls == ["https://example.com/cars", "https://example.com/cars?page=2", "https://example.com/cars?page=3"]


def test_catalog_model_names_strip_selected_brand_prefix():
    from src import live_marketplaces as lm
    assert lm._clean_model_catalog_name("BMW X5", "BMW") == "X5"
    assert lm._clean_model_catalog_name("BMW 3 Series", "BMW") == "3 Series"
    assert lm._clean_model_catalog_name("Mercedes-Benz E-Class", "Mercedes-Benz") == "E-Class"
    assert lm._clean_model_catalog_name("BMW X5 2019-2023 Discontinued", "BMW") is None
