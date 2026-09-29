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
