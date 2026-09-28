import json
from types import SimpleNamespace

from src.extractor import extract_image_urls, extract_page
from src.normalize import extract_price_lakh, extract_status, extract_labelled_date, normalize_model
from src.reporting import write_dashboard_json
from src.scoring import enrich_and_score, negotiation_band


def result(html="", markdown=""):
    return SimpleNamespace(
        html=html, markdown=markdown,
        redirected_url="https://example.com/detail/1",
        status_code=200, success=True,
        crawled_at="2026-09-28T00:00:00Z",
    )


def test_price_parser_prefers_asking_price_over_reservation():
    text = "Reservation Amount: ₹347500 (10% of ₹3475000) Asking Price ₹34.75 Lakh"
    assert extract_price_lakh(text) == 34.75


def test_status_parser_detects_sold_listing():
    assert extract_status("Vehicle is already sold to another customer") == (
        True, "sold/unavailable marker detected"
    )


def test_labelled_date_parser_handles_month_and_year():
    assert extract_labelled_date("Date of registration: Aug 2023", ["date of registration"]) == "2023-08"


def test_model_normalization_extracts_brand_model_variant():
    brand, model, variant = normalize_model(
        "BMW 220i M Sport Shadow Edition",
        "Premium used BMW 2 Series Gran Coupe in Delhi",
    )
    assert (brand, model, variant) == ("BMW", "2 Series", "M Sport")


def test_image_extractor_prefers_open_graph_and_filters_assets():
    html = """<html><head>
    <meta property="og:image" content="/cars/q3-main.jpg">
    </head><body>
    <img alt="dealer logo" src="/assets/logo.png" width="80" height="80">
    <img alt="Audi Q3 vehicle gallery" data-src="/cars/q3-side.webp" width="900" height="600">
    <img alt="icon" src="/icons/car.svg">
    </body></html>"""
    urls = extract_image_urls(html, "https://example.com/detail/1")
    assert urls[0] == "https://example.com/cars/q3-main.jpg"
    assert "https://example.com/cars/q3-side.webp" in urls
    assert all("logo" not in u and "icon" not in u for u in urls)


def test_extract_page_carries_listing_images_into_vehicle():
    v = extract_page(
        "test", 1, "https://example.com/gla",
        result(
            html='<meta property="og:image" content="https://cdn.example.com/car.jpg">',
            markdown="Mercedes-Benz GLA 220d AMG Line 4MATIC 2023 32,500 km Diesel ₹37.5 Lakh First owner Registration year 2023 Manufacturing Year 2023 Automatic",
        ),
    )
    assert v is not None
    assert v.image_urls == ["https://cdn.example.com/car.jpg"]


def scoring_settings():
    return SimpleNamespace(market={
        "reference_date": "2026-09-28",
        "low_mileage_km": 20000,
        "mileage_preference_km": 50000,
        "exceptional_discount_vs_comparables_pct": 15,
        "bargain_discount_vs_comparables_pct": 10,
        "min_comparables_for_price_call": 4,
    })


def base_vehicle(**overrides):
    data = dict(
        year_manufacture=2024, mileage_km=12000, price_lakh=32.0,
        owner_count=1, source_tier=1, certification=None,
        condition_signal=None, live_verified=True, data_consistent=True,
        sold_signal=False, comparable_count=0, comparable_median_lakh=None,
        comparable_low_lakh=None, comparable_high_lakh=None,
        discount_vs_comparable_pct=None, km_per_year=None,
        opportunity_score=None, opportunity_class=None, verification_notes=[],
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_scoring_zeroes_sold_vehicle():
    v = base_vehicle(sold_signal=True)
    enrich_and_score(v, [{"price_lakh": 40.0}] * 4, scoring_settings())
    assert v.opportunity_score == 0
    assert v.opportunity_class == "watch"


def test_scoring_requires_minimum_comparables_for_bargain_call():
    v = base_vehicle()
    enrich_and_score(v, [{"price_lakh": 40.0}] * 3, scoring_settings())
    assert v.opportunity_class != "bargain"
    assert v.opportunity_class == "low-mileage-watch"


def test_negotiation_band_is_below_asking_price():
    v = SimpleNamespace(price_lakh=34.75, opportunity_class="bargain")
    target, walk = negotiation_band(v)
    assert target < walk < v.price_lakh


def test_dashboard_json_preserves_images():
    from pathlib import Path
    import tempfile
    v = base_vehicle()
    v.brand="Audi"; v.model="Q3"; v.variant="40 TFSI Premium Plus"
    v.year_registration=2023; v.manufacture_date="2023-06"; v.registration_date="2023-10"
    v.location="Delhi NCR"; v.source_name="AutoBest"; v.url="https://example.com/q3"
    v.live_verified=True; v.comparable_count=4; v.comparable_median_lakh=36.5
    v.comparable_low_lakh=35; v.comparable_high_lakh=38; v.discount_vs_comparable_pct=4.8
    v.km_per_year=4500; v.opportunity_score=66; v.opportunity_class="low-mileage-watch"
    v.fuel="petrol"; v.transmission="automatic"; v.image_urls=["https://cdn.example.com/q3.jpg"]
    v.final_url=v.url; v.http_status=200; v.crawled_at="2026-09-28T00:00:00Z"
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "latest.json"
        write_dashboard_json(str(path), "2026-09-28", [v], [], lambda x: (33.0, 34.0), stats={"vehicles_seen": 1})
        payload = json.loads(path.read_text())
    assert payload["vehicles"][0]["image_urls"] == ["https://cdn.example.com/q3.jpg"]
    assert payload["stats"]["vehicles_seen"] == 1
