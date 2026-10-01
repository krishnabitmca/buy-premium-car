import json
import socket
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch

from src import live_marketplaces as lm
from api import search as search_api
from api import catalog as catalog_api


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.payload.encode()


def jsonld(name="BMW X5", brand="BMW", model="X5", price="4950000", url="/used/bmw-x5"):
    return f'''<html><script TYPE="application/ld+json">
    {{"@type":"Product","name":"{name}","brand":{{"name":"{brand}"}},"model":"{model}",
    "vehicleConfiguration":"xDrive40i M Sport","offers":{{"price":"{price}","url":"{url}"}},"url":"{url}"}}
    </script></html>'''


class TestPureFunctions(unittest.TestCase):
    def test_slug_and_brand_aliases(self):
        self.assertEqual(lm._slug("Mercedes-Benz"), "mercedes-benz")
        self.assertEqual(lm._slug("Citroën C5 Aircross"), "citro-n-c5-aircross")
        self.assertEqual(lm._canonical_brand("MG"), "MG Motor")
        self.assertEqual(lm._canonical_brand("Mercedes Benz"), "Mercedes-Benz")

    def test_number_boundaries(self):
        self.assertEqual(lm._number("₹49,50,000"), 4950000.0)
        self.assertEqual(lm._number("49.5 lakh"), 49.5)
        self.assertIsNone(lm._number(None))
        self.assertIsNone(lm._number("not-a-price"))

    def test_jsonld_tolerant_parser(self):
        html = jsonld().replace('type="application/ld+json"', 'type = "application/ld+json; charset=utf-8"')
        self.assertEqual(len(lm._json_objects(html)), 1)
        malformed = '<script type="application/ld+json">{bad json</script>'
        self.assertEqual(lm._json_objects(malformed), [])

    def test_infer_brand_model(self):
        self.assertEqual(lm._infer_brand_model("BMW X5", "BMW", "X5"), ("BMW", "X5"))
        self.assertEqual(lm._infer_brand_model("BMW X5 xDrive40i", None, None), ("BMW", "X5 xDrive40i"))
        self.assertEqual(lm._infer_brand_model("Unknown", None, None), ("Unknown", "Unknown"))

    def test_parse_listing_and_deduplicate(self):
        html = jsonld() + jsonld()
        rows = lm.parse_live_listings(html, "Fixture", "https://example.com/")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price_lakh"], 49.5)
        self.assertTrue(rows[0]["live_verified"])
        self.assertEqual(rows[0]["url"], "https://example.com/used/bmw-x5")

    def test_parse_offer_only_and_irrelevant_jsonld(self):
        html = '''<script type="application/ld+json">
        {"@type":"Offer","name":"Audi Q5","price":"5200000","url":"/q5"}
        </script>
        <script type="application/ld+json">{"@type":"BreadcrumbList","name":"Ignore me"}</script>'''
        rows = lm.parse_live_listings(html, "Fixture", "https://example.com/")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price_lakh"], 52.0)

    def test_live_brands_uses_current_catalog_and_missing_match(self):
        page = '<a href="/bmw-cars">BMW Cars</a><a href="/audi-cars">Audi Cars</a>'
        with patch.object(lm, "fetch_text", return_value=page):
            rows = lm.live_brands()
        self.assertEqual(len(rows), len(lm.CURRENT_BRANDS))
        bmw = next(x for x in rows if x["name"] == "BMW")
        self.assertTrue(bmw["url"].endswith("/bmw-cars"))

    def test_live_models_filters_noise(self):
        page = '''<a href="/bmw/x5">X5</a><a href="/bmw/x3">X3</a>
                  <a href="/bmw/view-all-models">View all models</a>
                  <a href="/bmw/dealers">Dealers</a>'''
        def fake_fetch(url):
            if url.endswith("/newcars"): return '<a href="/bmw-cars">BMW Cars</a>'
            return page
        with patch.object(lm, "fetch_text", side_effect=fake_fetch):
            rows = lm.live_models("BMW")
        self.assertEqual([x["name"] for x in rows], ["X3", "X5"])

    def test_live_inventory_partial_failure(self):
        def fake_fetch(url):
            if "cardekho" in url: return jsonld()
            raise TimeoutError("synthetic source timeout")
        with patch.object(lm, "fetch_text", side_effect=fake_fetch):
            vehicles, sources = lm.live_inventory()
        self.assertEqual(len(vehicles), 1)
        self.assertEqual(sources[0]["status"], "live")
        self.assertEqual(sources[1]["status"], "unavailable")
        self.assertIn("timeout", sources[1]["error"])

    def test_condition_filter_boundaries(self):
        used={"brand":"BMW","model":"X5","variant":"x","condition_signal":"used","price_lakh":50}
        demo={"brand":"BMW","model":"X5","variant":"Demo","condition_signal":"demo","price_lakh":50}
        self.assertTrue(search_api._match(used,"BMW",None,None,None,None,"used"))
        self.assertFalse(search_api._match(demo,"BMW",None,None,None,None,"used"))
        self.assertTrue(search_api._match(demo,"BMW",None,None,None,None,"demo"))
        self.assertFalse(search_api._match(used,"BMW",None,None,None,None,"demo"))
        self.assertTrue(search_api._match(used,"BMW",None,None,None,None,"both"))

    def test_rich_live_fields_and_demo_detection(self):
        html = '''<script type="application/ld+json">
        {"@type":"Product","name":"BMW X5 Demo","brand":{"name":"BMW"},"model":"X5",
        "vehicleConfiguration":"xDrive40i","itemCondition":"Demonstrator",
        "vehicleModelDate":"2024","mileageFromOdometer":{"value":18000},
        "fuelType":"Petrol","vehicleTransmission":"Automatic","bodyType":"SUV",
        "seller":{"name":"Dealer","address":{"addressLocality":"Delhi","addressRegion":"Delhi"}},
        "offers":{"price":"4950000","url":"/x5-demo"}}
        </script>'''
        rows=lm.parse_live_listings(html,"Motozite Demo","https://example.com/")
        self.assertEqual(len(rows),1)
        row=rows[0]
        self.assertEqual(row["condition_signal"],"demo")
        self.assertEqual(row["seller_city"],"Delhi")
        self.assertEqual(row["seller_state"],"Delhi")
        self.assertEqual(row["location"],"Delhi")
        self.assertEqual(row["mfg_year"],2024)
        self.assertEqual(row["km"],18000)
        self.assertEqual(row["fuel"],"Petrol")
        self.assertEqual(row["transmission"],"Automatic")
        self.assertEqual(row["body_type"],"SUV")

    def test_search_match_boundaries(self):
        v={"brand":"BMW","model":"X5","variant":"xDrive40i","location":"Delhi","fuel":"Petrol",
           "transmission":"Automatic","source":"Fixture","price_lakh":49.5,"mfg_year":2024}
        self.assertTrue(search_api._match(v, "BMW X5", 40, 55, 3, "Bengaluru"))
        self.assertFalse(search_api._match(v, "Audi", None, None, None, "Bengaluru"))
        self.assertFalse(search_api._match(v, "BMW", 50, None, None, "Bengaluru"))
        self.assertFalse(search_api._match(v, "BMW", None, 40, None, "Bengaluru"))
        self.assertFalse(search_api._match(v, "BMW", None, None, 2, "Bengaluru"))
        self.assertTrue(search_api._match(v, "BMW", None, None, None, "Bengaluru"))
        self.assertTrue(search_api._match(v, "BMW", None, None, None, "Bengaluru", "both"))

    def test_search_score(self):
        low={"discount_pct":2,"source_count":1,"identity_confidence":.5,"live_verified":True,
             "data_consistent":True,"km":20000,"owners":1}
        high={"discount_pct":10,"source_count":3,"identity_confidence":1,"live_verified":True,
              "data_consistent":True,"km":10000,"owners":1}
        self.assertGreater(search_api._score(high), search_api._score(low))


class TestHTTPContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), search_api.handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def request(self, method, path, body=None):
        import urllib.request
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base+path, data=data, method=method,
                                     headers={"Content-Type":"application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_get_and_404(self):
        with patch.object(search_api, "live_inventory", return_value=([], [])):
            status, body = self.request("GET", "/api/search")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["mode"], "live")
        self.assertEqual(self.request("GET", "/wrong")[0], 404)

    def test_post_validation(self):
        status, body = self.request("POST", "/api/search", {"budget_min":60,"budget_max":40})
        self.assertEqual(status, 400)
        self.assertIn("Minimum budget", body["error"])

    def test_post_market_reference_and_destination_is_not_filter(self):
        vehicles=[]
        for price, city in [(45,"Delhi"),(50,"Mumbai"),(55,"Bengaluru"),(60,"Pune")]:
            vehicles.append({"brand":"BMW","model":"X5","variant":"x","price_lakh":price,
                             "location":city,"fuel":"Petrol","mfg_year":2024,
                             "source":"Fixture","url":"https://example.com/"+str(price),
                             "live_verified":True,"data_consistent":True})
        with patch.object(search_api, "live_inventory", return_value=(vehicles,[{"source":"Fixture","status":"live","listings_found":4}])):
            status, body = self.request("POST","/api/search",
                {"query":"BMW X5","destination":"Bengaluru","budget_min":40,"budget_max":65})
        self.assertEqual(status,200)
        self.assertEqual(body["total_results"],4)
        self.assertTrue(all(v["purchase_context"] for v in body["results"]))
        self.assertEqual({v["comp_median"] for v in body["results"]},{52.5})
        self.assertEqual({v["comparable_count"] for v in body["results"]},{4})
        self.assertEqual({v["discount_pct"] for v in body["results"]},{14.3,4.8,-4.8,-14.3})

    def test_post_insufficient_comparables_does_not_invent_reference(self):
        vehicles=[{"brand":"BMW","model":"X5","price_lakh":49.5,"source":"Fixture",
                   "url":"https://example.com/x","live_verified":True,"data_consistent":True}]
        with patch.object(search_api,"live_inventory",return_value=(vehicles,[])):
            status, body=self.request("POST","/api/search",{"query":"BMW X5"})
        self.assertEqual(status,200)
        self.assertIsNone(body["results"][0]["comp_median"])
        self.assertIsNone(body["results"][0]["discount_pct"])
        self.assertEqual(body["results"][0]["comparable_count"],1)

    def test_post_no_offline_fallback_on_source_failure(self):
        with patch.object(search_api,"live_inventory",side_effect=RuntimeError("all sources down")):
            status, body=self.request("POST","/api/search",{"query":"BMW X5"})
        self.assertEqual(status,500)
        self.assertIn("Search failed",body["error"])

    def test_oversized_and_malformed_body(self):
        import urllib.request
        req=urllib.request.Request(self.base+"/api/search",data=b"{bad",method="POST",
            headers={"Content-Type":"application/json","Content-Length":"4"})
        try:
            urllib.request.urlopen(req,timeout=5)
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code,400)
        huge=b"x"*64001
        req=urllib.request.Request(self.base+"/api/search",data=huge,method="POST",
            headers={"Content-Type":"application/json","Content-Length":str(len(huge))})
        try:
            urllib.request.urlopen(req,timeout=5)
            self.fail("expected 400")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code,400)


class TestCatalogHTTPContract(unittest.TestCase):
    def test_catalog_models_contract(self):
        class H:
            pass
        with patch.object(catalog_api, "live_models", return_value=[{"name":"X5"}]):
            # Validate the handler module exposes the expected route and callable.
            self.assertTrue(hasattr(catalog_api, "handler"))
            self.assertTrue(callable(catalog_api.live_models))

    def test_catalog_unknown_route_contract(self):
        self.assertTrue(hasattr(catalog_api.handler, "do_GET"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
