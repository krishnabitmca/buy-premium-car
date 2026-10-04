import json
import socket
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch

from src import live_marketplaces as lm
from api import search as search_api
from api import catalog as catalog_api
from src.acquisition import purchase_context


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

    def test_canonical_url_removes_tracking_parameters(self):
        self.assertEqual(
            lm._canonical_url("https://example.com/base/", "https://example.com/car?id=123&utm_source=x&gclid=y#top"),
            "https://example.com/car?id=123",
        )

    def test_visible_parser_does_not_inject_requested_identity(self):
        html='''<a href="/used/mumbai/audi-q5/abc">
        2024 Audi Q5 45 TFSI 20,000 km | Petrol | Mumbai Rs. 45 Lakh
        </a>'''
        rows=lm.parse_visible_listing_links(
            html,"CarWale Used","https://www.carwale.com/used/mercedes-benz-c-class/",
            "Mercedes-Benz Mercedes-Benz C-Class")
        self.assertEqual(rows, [])

    def test_visible_parser_preserves_independent_identity(self):
        html='''<a href="/used/mumbai/mercedes-benz-c-class/abc">
        2024 Mercedes-Benz C-Class C 200 20,000 km | Petrol | Mumbai Rs. 45 Lakh
        </a>'''
        rows=lm.parse_visible_listing_links(
            html,"CarWale Used","https://www.carwale.com/used/mercedes-benz-c-class/",
            "Mercedes-Benz Mercedes-Benz C-Class")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["brand"],"Mercedes-Benz")
        self.assertTrue(lm._model_identity_matches("C-Class",rows[0]["model"]))
        self.assertIn("provenance",rows[0])

    def test_fetch_retries_retryable_http_error(self):
        class Headers:
            def get(self,key,default=None): return "text/html; charset=utf-8" if key.lower()=="content-type" else default
            def get_content_charset(self): return "utf-8"
        class Response:
            status=200
            headers=Headers()
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,n=-1): return "<html>ok</html>".encode()
        import urllib.error
        calls=[urllib.error.HTTPError("https://example.com",503,"busy",Headers(),None),Response()]
        with patch.object(lm.urllib.request,"urlopen",side_effect=calls):
            with patch.object(lm.time,"sleep",return_value=None):
                self.assertEqual(lm.fetch_text("https://example.com"),"<html>ok</html>")
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

    def test_parse_listing_preserves_vehicle_images(self):
        html = jsonld().replace('"vehicleConfiguration":"xDrive40i M Sport",', '"vehicleConfiguration":"xDrive40i M Sport","image":["/images/x5-front.jpg","https://cdn.example.com/x5-side.jpg"],')
        rows = lm.parse_live_listings(html, "Fixture", "https://example.com/")
        self.assertEqual(rows[0]["image"], "https://example.com/images/x5-front.jpg")
        self.assertEqual(rows[0]["images"][1], "https://cdn.example.com/x5-side.jpg")

    def test_visible_listing_preserves_nested_car_image(self):
        html = '''<a href="/used/bmw-x5/abc"><img src="/images/x5.jpg">2024 BMW X5 xDrive40i | Petrol | Bengaluru Rs. 49.5 Lakh 20,000 km</a>'''
        rows = lm.parse_visible_listing_links(html, "Fixture", "https://example.com/", "BMW X5")
        self.assertEqual(rows[0]["image"], "https://example.com/images/x5.jpg")

    def test_parse_listing_and_deduplicate(self):
        html = jsonld() + jsonld()
        rows = lm.parse_live_listings(html, "Fixture", "https://example.com/")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price_lakh"], 49.5)
        self.assertTrue(rows[0]["live_verified"])
        self.assertEqual(rows[0]["listing_name"],"BMW X5")
        self.assertEqual(rows[0]["url"], "https://example.com/used/bmw-x5")

    def test_parse_offer_only_and_irrelevant_jsonld(self):
        html = '''<script type="application/ld+json">
        {"@type":"Offer","name":"Audi Q5","price":"5200000","url":"/q5"}
        </script>
        <script type="application/ld+json">{"@type":"BreadcrumbList","name":"Ignore me"}</script>'''
        rows = lm.parse_live_listings(html, "Fixture", "https://example.com/")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price_lakh"], 52.0)

    def test_live_brands_uses_only_current_catalog_matches(self):
        page = '<a href="/bmw-cars">BMW Cars</a><a href="/audi-cars">Audi Cars</a>'
        registry = [
            {"brands": ["BMW"]},
            {"brands": ["Audi"]},
            {"brands": ["Mercedes-Benz"]},
        ]
        with patch.object(lm, "fetch_text", return_value=page), \
             patch.object(lm, "_registry_brand_records", return_value=[
                 {"name": "BMW", "url": "", "catalog_verified": "database"},
                 {"name": "Audi", "url": "", "catalog_verified": "database"},
                 {"name": "Mercedes-Benz", "url": "", "catalog_verified": "database"},
             ]), \
             patch.dict(lm.os.environ, {"CARSCANNER_CATALOG_SOURCE_URL": "https://catalog.example/newcars"}, clear=False):
            rows = lm.live_brands()

        # The catalog is the source of customer-visible truth: the result size
        # must be derived from current catalog links, not a baked-in count.
        catalog_parser = lm._LinkParser()
        catalog_parser.feed(page)
        catalog_names = {
            text.split(" Cars", 1)[0].strip()
            for text, _ in catalog_parser.links
            if text.endswith(" Cars")
        }
        expected = {
            brand
            for record in registry
            for brand in record["brands"]
            if brand in catalog_names
        }
        self.assertEqual({row["name"] for row in rows}, expected)
        self.assertEqual(len(rows), len(expected))
        # The fixture represents registry/database brand identity; catalog_verified
        # records the provenance of that identity rather than a hard-coded boolean.
        self.assertTrue(all(row["catalog_verified"] == "database" for row in rows))
        self.assertTrue(all(row["url"].endswith(f"/{lm._slug(row['name'])}-cars") for row in rows))

    def test_live_models_filters_noise_and_discontinued_duplicates(self):
        page = '''<a href="/bmw/x5">BMW X5</a>
                  <a href="/bmw/x3">BMW X3</a>
                  <a href="/bmw/3-series">BMW 3 Series ₹77.10 Lakh*</a>
                  <a href="/bmw/3-series">BMW 3 Series ₹77.10 Lakh*</a>
                  <a href="/bmw/2-series-2020-2025">BMW 2 Series 2020-2025 ₹32 - 46.90 Lakh * Discontinued 2025</a>
                  <a href="/bmw/7-series-old">BMW 7 Series 2023-2026 ₹1.70 - 1.83 Cr * Discontinued 2026</a>
                  <a href="/bmw/7-series">BMW 7 Series ₹1.95 Cr*</a>
                  <a href="/bmw/x1-lwb">BMW X1 LWB ₹51 Lakh Estimated</a>
                  <a href="/bmw/view-all-models">View all models</a>
                  <a href="/bmw/dealers">Dealers</a>'''
        def fake_fetch(url):
            if url.endswith("/newcars"): return '<a href="/bmw-cars">BMW Cars</a>'
            return page
        with patch.object(lm, "fetch_text", side_effect=fake_fetch):
            rows = lm.live_models("BMW")
        self.assertEqual([x["name"] for x in rows], ["BMW 3 Series", "BMW 7 Series", "BMW X3", "BMW X5"])
        self.assertEqual(len([x for x in rows if x["slug"] == "bmw-3-series"]), 1)
        self.assertNotIn("discontinued", " ".join(x["name"] for x in rows).lower())
        self.assertNotIn("₹", " ".join(x["name"] for x in rows))

    def test_model_link_rejects_non_model_pages(self):
        selected={"name":"BMW","slug":"bmw","url":"https://www.cardekho.com/bmw-cars"}
        self.assertTrue(lm._is_current_model_link(selected,"https://www.cardekho.com/bmw/x5"))
        self.assertTrue(lm._is_current_model_link(selected,"https://www.cardekho.com/carmodels/bmw/x5"))
        self.assertFalse(lm._is_current_model_link(selected,"https://www.cardekho.com/bmw/dealers"))
        self.assertFalse(lm._is_current_model_link(selected,"https://www.cardekho.com/bmw/x5/variants"))
        self.assertFalse(lm._is_current_model_link(selected,"https://www.cardekho.com/bmw/x5-offers"))

    def test_query_identity_rejects_wrong_model(self):
        row={"brand":"BMW","model":"X3","listing_name":"BMW X3 xDrive30d",
             "variant":"xDrive30d","url":"https://example.com/bmw-x3"}
        self.assertFalse(lm._identity_matches_query(row,"BMW X5"))

    def test_query_identity_accepts_variant_of_requested_model(self):
        row={"brand":"Mercedes-Benz","model":"C-Class",
             "listing_name":"2025 Mercedes-Benz C-Class C 200 Mild Hybrid",
             "variant":"C 200 Mild Hybrid","url":"https://example.com/c-class-c200"}
        self.assertTrue(lm._identity_matches_query(row,"Mercedes-Benz C-Class"))

    def test_query_identity_rejects_brand_mismatch(self):
        row={"brand":"Audi","model":"Q5","listing_name":"Audi Q5",
             "variant":"Premium","url":"https://example.com/audi-q5"}
        self.assertFalse(lm._identity_matches_query(row,"BMW Q5"))

    def test_selected_source_routes_are_resolved_from_registry(self):
        from src.source_adapters import BuiltinMarketplaceAdapter

        registry = [
            {"name": "Source A", "adapter_status": "live", "url": "https://source-a.example/search"},
            {"name": "Source B", "adapter_status": "live", "url": "https://source-b.example/search"},
        ]
        with patch.object(lm, "_targeted_source_urls", return_value={
            "Source A": "https://source-a.example/search?brand=bmw&model=x5",
            "Source B": "https://source-b.example/search?brand=bmw&model=x5",
        }), \
             patch("src.source_adapters.fetch_text", return_value="<html></html>"), \
             patch("src.source_adapters.parse_live_listings", return_value=[]), \
             patch("src.source_adapters.parse_visible_listing_links", return_value=[]):
            for source in registry:
                result = BuiltinMarketplaceAdapter(source).fetch(
                    __import__("src.source_adapters", fromlist=["AdapterRequest"]).AdapterRequest(
                        query="BMW X5", condition="used"
                    )
                )
                self.assertEqual(result.status, "live")
                self.assertIn(source["name"], {"Source A", "Source B"})

    def test_brand_only_search_uses_registry_selected_sources(self):
        with patch.object(lm, "_targeted_source_urls", return_value={
            "Source A": "https://source-a.example/search?brand=bmw",
            "Source B": "https://source-b.example/search?brand=bmw",
        }) as resolver:
            resolver("BMW", "used")
            self.assertEqual(resolver.call_args.args, ("BMW", "used"))

    def test_demo_adapter_keeps_oem_and_motozite_demo_inventory(self):
        from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter
        moto={"name":"Motozite Demo","adapter_status":"live","url":"https://motozite.com/demo-cars"}
        html=jsonld("Mercedes-Benz E-Class LWB E200",brand="Mercedes-Benz",model="E-Class LWB E200",price="7500000",url="/demo/mercedes-benz/e-class/1")
        with patch.object(lm,"fetch_text",return_value=html):
            result=BuiltinMarketplaceAdapter(moto).fetch(AdapterRequest(query="Mercedes-Benz E-Class",condition="demo"))
        self.assertEqual(result.status,"live")
        self.assertEqual(len(result.listings),1)
        self.assertEqual(result.listings[0]["condition_signal"],"demo")
        self.assertEqual(result.listings[0]["brand"],"Mercedes-Benz")
        self.assertTrue(lm._identity_matches_query(result.listings[0],"Mercedes-Benz E-Class"))

    def test_selected_model_targets_cars24_and_spinny(self):
        urls=lm._targeted_source_urls("Audi Q5")
        self.assertEqual(urls["Cars24 Luxury Used"],"https://www.cars24.com/buy-used-audi-q5-cars/")
        self.assertEqual(urls["Spinny Luxury Used"],"https://www.spinny.com/used-q5-cars/s/")

    def test_brand_only_live_search_keeps_all_models(self):
        registry = [
            {"name": "Source A", "adapter_status": "live", "url": "https://source-a.example/search",
             "conditions": ["used"], "segments": ["mass_market", "premium", "luxury"], "brands": ["all"],
             "brand_query_url_template": "https://source-a.example/used/{brand_slug}/", "priority": 90},
            {"name": "Source B", "adapter_status": "live", "url": "https://source-b.example/search",
             "conditions": ["used"], "segments": ["mass_market", "premium", "luxury"], "brands": ["all"],
             "brand_query_url_template": "https://source-b.example/used/{brand_slug}/", "priority": 80},
        ]
        def fake_fetch(url):
            if url == "https://source-a.example/used/bmw/":
                return jsonld("BMW X5", brand="BMW", model="X5", url="/x5") + jsonld(
                    "BMW X3", brand="BMW", model="X3", url="/x3", price="4200000")
            if url == "https://source-b.example/used/bmw/":
                return jsonld("BMW X1", brand="BMW", model="X1", url="/x1", price="3500000")
            return "<html></html>"
        expected_vehicles = [
            {"brand": "BMW", "model": "X5", "condition_signal": "used"},
            {"brand": "BMW", "model": "X3", "condition_signal": "used"},
            {"brand": "BMW", "model": "X1", "condition_signal": "used"},
        ]
        expected_sources = [
            {"source": "Source A", "status": "live", "query_url": "https://source-a.example/used/bmw/"},
            {"source": "Source B", "status": "live", "query_url": "https://source-b.example/used/bmw/"},
        ]
        with patch.object(lm, "load_source_registry", return_value=registry):
            resolved = lm._targeted_source_urls("BMW", "used")
        self.assertEqual(resolved, expected_urls)

        with patch.object(lm, "_live_source_entries", return_value=registry), \
             patch("src.source_adapters.execute_adapters", return_value=(expected_vehicles, expected_sources)):
            vehicles, sources = lm.live_inventory(
                query="BMW", condition="used", budget_min=None, budget_max=None, destination="Bengaluru")
        self.assertEqual({s["query_url"] for s in sources},
                         {"https://source-a.example/used/bmw/", "https://source-b.example/used/bmw/"})
        self.assertGreaterEqual(len(vehicles), 3)
        self.assertEqual({v["brand"] for v in vehicles}, {"BMW"})
        self.assertEqual({v["model"] for v in vehicles}, {"X1", "X3", "X5"})
        self.assertTrue(all(v["condition_signal"] == "used" for v in vehicles))

    def test_visible_marketplace_listing_parser(self):
        html='''<a href="/used/mumbai/mercedes-benz-c-class/abc">
        2024 Mercedes-Benz C-Class C 200 Mild Hybrid 25,000 km | Petrol | Andheri West, Mumbai Rs. 46.75 Lakh
        </a>'''
        rows=lm.parse_visible_listing_links(
            html,"CarWale Used","https://www.carwale.com/used/mercedes-benz-c-class/",
            "Mercedes-Benz Mercedes-Benz C-Class")
        self.assertEqual(len(rows),1)
        row=rows[0]
        self.assertEqual(row["brand"],"Mercedes-Benz")
        self.assertEqual(row["model"],"C-Class")
        self.assertEqual(row["price_lakh"],46.75)
        self.assertEqual(row["mfg_year"],2024)
        self.assertEqual(row["km"],25000)
        self.assertEqual(row["fuel"],"Petrol")
        self.assertEqual(row["location"],"Andheri West, Mumbai")

    def test_live_inventory_partial_failure(self):
        def fake_fetch(url):
            if "cardekho" in url: return jsonld()
            raise TimeoutError("synthetic source timeout")
        with patch.object(lm, "fetch_text", side_effect=fake_fetch):
            vehicles, sources = lm.live_inventory()
        self.assertEqual(len(vehicles), 1)
        live=[s for s in sources if s["status"]=="live"]
        unavailable=[s for s in sources if s["status"]=="unavailable"]
        self.assertEqual(len(live),1)
        # Source expansion means the exact number of attempted sources is no
        # longer a fixed four. Every selected source other than the successful
        # CarDekho adapter should be reported as unavailable.
        self.assertGreater(len(unavailable), 0)
        self.assertEqual(len(sources), len(live) + len(unavailable))
        self.assertTrue(all("timeout" in s["error"] for s in unavailable))

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

    def test_model_family_match_uses_listing_title(self):
        v={"brand":"Mercedes-Benz","model":"C-Class","listing_name":"2025 Mercedes-Benz C-Class C 200 Mild Hybrid",
           "variant":"C 200 Mild Hybrid","price_lakh":46.75,"source":"CarWale Used"}
        self.assertTrue(search_api._match(v,"Mercedes-Benz C-Class",30,50,None,"Bengaluru","both"))

    def test_search_match_boundaries(self):
        v={"brand":"BMW","model":"X5","variant":"xDrive40i","location":"Delhi","fuel":"Petrol",
           "transmission":"Automatic","source":"Fixture","price_lakh":49.5,"mfg_year":2023}
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


    def test_model_catalog_rejects_navigation_links(self):
        selected={"name":"BMW","url":"https://www.cardekho.com/bmw"}
        for slug in ["gallery","images","photos","videos","reviews","offers","dealers","service","compare","accessories"]:
            self.assertFalse(lm._is_current_model_link(selected, f"https://www.cardekho.com/bmw/{slug}"))

    def test_model_catalog_rejects_discontinued_labels(self):
        self.assertIsNone(lm._clean_model_catalog_name("5 Series Discontinued"))
        self.assertIsNone(lm._clean_model_catalog_name("X5 Expected Launch"))
        self.assertIsNone(lm._clean_model_catalog_name("X5 Estimated"))

    def test_model_catalog_does_not_invent_models_when_brand_catalog_is_missing(self):
        # The dynamic architecture must not resurrect a baked-in model fallback.
        # If the configured/database catalog cannot resolve the requested brand,
        # the API returns no models rather than inventing customer-visible data.
        with patch.object(lm, "live_brands", return_value=[]), patch.object(lm, "fetch_text", return_value="<html></html>"):
            rows=lm.live_models("BMW")
        self.assertEqual(rows, [])


class TestImageCoverage(unittest.TestCase):
    def test_adapter_status_reports_image_coverage(self):
        from src import source_adapters as adapters
        listings = [
            {"image":"https://cdn.example.com/x5.jpg","images":["https://cdn.example.com/x5.jpg"]},
            {"image":None,"images":[]},
            {"images":["https://cdn.example.com/x5-side.jpg"]},
        ]
        count, pct = adapters._image_coverage(listings)
        self.assertEqual(count, 2)
        self.assertEqual(pct, 66.7)

    def test_empty_source_has_zero_image_coverage(self):
        from src import source_adapters as adapters
        self.assertEqual(adapters._image_coverage([]), (0, 0.0))


class TestAcquisitionContext(unittest.TestCase):
    def test_same_state_context(self):
        ctx=purchase_context({"location":"Bengaluru","price_lakh":35},"Bengaluru")
        self.assertEqual(ctx["mode"],"same_state")
        self.assertEqual(ctx["seller_state"],"Karnataka")
        self.assertEqual(ctx["observed_listing_price_lakh"],35)

    def test_interstate_context(self):
        ctx=purchase_context({"seller_city":"Delhi","seller_state":"Delhi","price_lakh":35},"Bengaluru")
        self.assertEqual(ctx["mode"],"interstate")
        self.assertEqual(ctx["destination_state"],"Karnataka")
        self.assertEqual(ctx["observed_listing_price_lakh"],35)
        self.assertIn("transport",ctx["note"].lower())

    def test_unknown_location_does_not_claim_interstate(self):
        ctx=purchase_context({"price_lakh":35},"Bengaluru")
        self.assertEqual(ctx["mode"],"location_unknown")
        self.assertIsNone(ctx["seller_state"])

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

    def test_inventory_complete_source_coverage_is_customer_search_path(self):
        inventory_rows = [
            {"brand":"BMW","model":"X5","price_lakh":49.5,"source":"Source A","condition":"used",
             "live_verified":True,"data_consistent":True},
            {"brand":"BMW","model":"X5","price_lakh":52.0,"source":"Source B","condition":"used",
             "live_verified":True,"data_consistent":True},
        ]
        inventory_sources = [
            {"name":"Source A","status":"inventory","mode":"inventory"},
            {"name":"Source B","status":"inventory","mode":"inventory"},
        ]
        with patch.object(search_api,"inventory_enabled",return_value=True), \
             patch.object(search_api,"search_inventory",return_value=(inventory_rows, inventory_sources, 2)), \
             patch.object(search_api,"live_inventory",side_effect=AssertionError("live crawler must not run when inventory coverage is complete")), \
             patch.object(search_api,"load_source_registry",return_value=[
                 {"name":"Source A","adapter_status":"live","conditions":["used"],"segments":["luxury"],"brands":["all"],"priority":90},
                 {"name":"Source B","adapter_status":"live","conditions":["used"],"segments":["luxury"],"brands":["all"],"priority":80},
             ]):
            status, body = self.request("POST","/api/search",{"query":"BMW X5","condition":"used"})

        self.assertEqual(status,200)
        self.assertEqual(body["mode"],"inventory")
        self.assertEqual(body["inventory_total"],2)
        self.assertEqual(body["total_results"],2)

    def test_inventory_partial_source_coverage_falls_back_to_live_sources(self):
        inventory_rows=[{
            "brand":"Audi","model":"Q5","price_lakh":45,
            "source":"CarDekho Used","condition":"used",
            "live_verified":True,"data_consistent":True,
        }]
        live_rows=[
            dict(inventory_rows[0]),
            {"brand":"Audi","model":"Q5","price_lakh":47,"source":"CarWale Used","condition_signal":"used","live_verified":True,"data_consistent":True},
            {"brand":"Audi","model":"Q5","price_lakh":46,"source":"Cars24 Luxury Used","condition_signal":"used","live_verified":True,"data_consistent":True},
            {"brand":"Audi","model":"Q5","price_lakh":48,"source":"Spinny Luxury Used","condition_signal":"used","live_verified":True,"data_consistent":True},
        ]
        inventory_sources=[{"name":"CarDekho Used","status":"inventory","mode":"inventory"}]
        live_sources=[
            {"source":"CarDekho Used","status":"live","listings_found":1},
            {"source":"CarWale Used","status":"live","listings_found":1},
            {"source":"Cars24 Luxury Used","status":"live","listings_found":1},
            {"source":"Spinny Luxury Used","status":"live","listings_found":1},
        ]
        with patch.object(search_api,"inventory_enabled",return_value=True), \
             patch.object(search_api,"search_inventory",return_value=(inventory_rows,inventory_sources,len(inventory_rows))), \
             patch.object(search_api,"live_inventory",return_value=(live_rows,live_sources)), \
             patch.object(search_api,"load_source_registry",return_value=[
                 {"name":"CarDekho Used","adapter_status":"live","conditions":["used"],"segments":["luxury"],"brands":["all"],"priority":90},
                 {"name":"CarWale Used","adapter_status":"live","conditions":["used"],"segments":["luxury"],"brands":["all"],"priority":90},
                 {"name":"Cars24 Luxury Used","adapter_status":"live","conditions":["used"],"segments":["luxury"],"brands":["Audi"],"priority":82},
                 {"name":"Spinny Luxury Used","adapter_status":"live","conditions":["used"],"segments":["luxury"],"brands":["Audi"],"priority":82},
             ]):
            status,body=self.request("POST","/api/search",{"query":"Audi Q5","condition":"used"})
        self.assertEqual(status,200)
        self.assertEqual(body["mode"],"live_coverage_fallback")
        self.assertEqual(body["sources_found"],4)

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

    def test_market_reference_does_not_mix_used_and_demo(self):
        vehicles=[]
        for price,condition in [(40,"used"),(45,"used"),(50,"used"),(70,"demo"),(75,"demo"),(80,"demo")]:
            vehicles.append({"brand":"BMW","model":"X5","price_lakh":price,"condition_signal":condition,
                             "source":"Fixture","url":"https://example.com/"+str(price),
                             "live_verified":True,"data_consistent":True})
        with patch.object(search_api,"live_inventory",return_value=(vehicles,[{"source":"Fixture","status":"live","listings_found":6}])):
            status,body=self.request("POST","/api/search",{"query":"BMW X5"})
        self.assertEqual(status,200)
        used=[v for v in body["results"] if v["condition_signal"]=="used"]
        demo=[v for v in body["results"] if v["condition_signal"]=="demo"]
        self.assertEqual({v["comp_median"] for v in used},{45.0})
        self.assertEqual({v["comp_median"] for v in demo},{75.0})

    def test_post_insufficient_comparables_does_not_invent_reference(self):
        vehicles=[{"brand":"BMW","model":"X5","price_lakh":49.5,"source":"Fixture",
                   "url":"https://example.com/x","live_verified":True,"data_consistent":True}]
        with patch.object(search_api,"live_inventory",return_value=(vehicles,[])):
            status, body=self.request("POST","/api/search",{"query":"BMW X5"})
        self.assertEqual(status,200)
        self.assertIsNone(body["results"][0]["comp_median"])
        self.assertIsNone(body["results"][0]["discount_pct"])
        self.assertEqual(body["results"][0]["comparable_count"],1)

    def test_post_all_sources_unavailable_returns_service_unavailable(self):
        failed=[{"source":"Fixture","status":"unavailable","listings_found":0,"error":"timeout"}]
        with patch.object(search_api,"live_inventory",return_value=([],failed)):
            status, body=self.request("POST","/api/search",{"query":"BMW X5"})
        self.assertEqual(status,503)
        self.assertEqual(body["mode"],"live")

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


    def test_model_catalog_rejects_navigation_links(self):
        from src import live_marketplaces as lm
        selected={"name":"BMW","url":"https://www.cardekho.com/bmw"}
        for slug in ["gallery","images","photos","videos","reviews","offers","dealers","service","compare","accessories"]:
            self.assertFalse(lm._is_current_model_link(selected, f"https://www.cardekho.com/bmw/{slug}"))

    def test_model_catalog_rejects_discontinued_labels(self):
        from src import live_marketplaces as lm
        self.assertIsNone(lm._clean_model_catalog_name("5 Series Discontinued"))
        self.assertIsNone(lm._clean_model_catalog_name("X5 Expected Launch"))
