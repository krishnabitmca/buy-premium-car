import json
import unittest

from src import live_marketplaces as lm


class TestEmbeddedMarketplaceParser(unittest.TestCase):
    def test_spinny_next_data_listing_with_image(self):
        payload = {
            "props": {"pageProps": {"cars": [{
                "title": "2019 BMW X1 sDrive20i xLine",
                "brand": "BMW",
                "model": "X1",
                "price": 2450000,
                "year": 2019,
                "km": 32000,
                "city": "Bengaluru",
                "url": "/cars/used-bmw-x1-12345",
                "image": "https://cdn.example.com/x1.jpg",
            }]}}
        }
        html = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(payload) + "</script>"
        rows = lm.parse_embedded_marketplace_listings(
            html, "Spinny Luxury Used", "https://www.spinny.com/used-bmw-cars/s/", "BMW X1"
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["brand"], "BMW")
        self.assertEqual(row["model"], "X1")
        self.assertEqual(row["price_lakh"], 24.5)
        self.assertEqual(row["mfg_year"], 2019)
        self.assertEqual(row["km"], 32000)
        self.assertEqual(row["location"], "Bengaluru")
        self.assertEqual(row["image"], "https://cdn.example.com/x1.jpg")
        self.assertEqual(row["condition_signal"], "used")

    def test_embedded_parser_rejects_non_listing_json(self):
        payload = {"props": {"pageProps": {"seo": {
            "title": "BMW used cars", "price": 100, "url": "/used-bmw-cars/s/"
        }}}}
        html = '<script type="application/json">' + json.dumps(payload) + "</script>"
        rows = lm.parse_embedded_marketplace_listings(
            html, "Spinny Luxury Used", "https://www.spinny.com/", "BMW X1"
        )
        self.assertEqual(rows, [])

    def test_embedded_parser_preserves_demo_condition(self):
        payload = {"cars": [{
            "title": "2025 Mercedes-Benz E-Class Demo",
            "brand": "Mercedes-Benz",
            "model": "E-Class",
            "price": 7350000,
            "year": 2025,
            "url": "/demo/e-class-1",
            "image": "https://cdn.example.com/e.jpg",
            "condition": "demo",
        }]}
        html = '<script type="application/json">' + json.dumps(payload) + "</script>"
        rows = lm.parse_embedded_marketplace_listings(
            html, "Motozite Demo", "https://motozite.com/", "Mercedes-Benz E-Class"
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["condition_signal"], "demo")


if __name__ == "__main__":
    unittest.main()
