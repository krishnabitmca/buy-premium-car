from src.live_marketplaces import _infer_condition, parse_visible_listing_links


def test_oem_source_name_does_not_make_used_listing_demo():
    row = {"name": "2023 BMW X5 xDrive30d", "description": "BMW Premium Selection certified pre-owned vehicle"}
    assert _infer_condition(row, "BMW Premium Selection Demo") == "used"


def test_listing_level_demonstrator_evidence_wins():
    row = {"name": "2024 BMW X5 xDrive40i", "description": "Dealer demonstrator vehicle, 4,500 km"}
    assert _infer_condition(row, "BMW Premium Selection") == "demo"


def test_mixed_oem_inventory_keeps_used_and_demo_separate():
    used = {"name": "2022 Mercedes-Benz E-Class", "description": "Certified pre-owned vehicle"}
    demo = {"name": "2025 Mercedes-Benz E-Class", "description": "Demonstrator car"}
    assert _infer_condition(used, "Mercedes-Benz Used Cars") == "used"
    assert _infer_condition(demo, "Mercedes-Benz Used Cars") == "demo"


def test_demo_words_in_source_name_are_not_listing_evidence():
    html = '<a href="/car/1">2023 BMW X5 | Diesel | Bengaluru ₹ 65 Lakh | 12000 km Automatic</a>'
    rows = parse_visible_listing_links(html, "OEM Demo Inventory", "https://example.com", "BMW X5")
    assert rows
    assert rows[0]["condition_signal"] == "unknown"


def test_unlabelled_listing_is_unknown_not_used_or_demo():
    row = {"name": "2025 BMW X1 xLine", "description": "4,500 km, automatic, Bengaluru"}
    assert _infer_condition(row, "BMW Premium Selection Demo") == "unknown"


def test_unregistered_alone_is_not_demonstrator_evidence():
    row = {"name": "2026 BMW X1 xLine", "description": "Unregistered vehicle, 50 km"}
    assert _infer_condition(row, "BMW Premium Selection") == "unknown"


def test_unregistered_with_explicit_demonstrator_evidence_is_demo():
    row = {"name": "2026 BMW X1 xLine", "description": "Unregistered dealer demonstrator vehicle, 1,200 km"}
    assert _infer_condition(row, "BMW Premium Selection") == "demo"


def test_detail_page_title_is_listing_level_demo_evidence():
    from src.live_marketplaces import parse_live_listings
    html='''<html><head><title>BMW X1 Luxury Demo Car Price & Specs</title></head><body>
    <script type="application/ld+json">{"@type":"Vehicle","name":"BMW X1 sDrive18i M Sport","offers":{"price":"4800000","url":"https://dealer.example/x1-demo"}}</script>
    </body></html>'''
    rows=parse_live_listings(html,"Generic Dealer","https://dealer.example/x1-demo")
    assert rows[0]["condition_signal"]=="demo"


def test_footer_demo_text_does_not_override_explicit_used_listing():
    from src.live_marketplaces import parse_live_listings
    html='''<html><head><title>Used BMW X1 for sale</title></head><body>
    <script type="application/ld+json">{"@type":"Vehicle","name":"BMW X1","condition":"used","offers":{"price":"2500000","url":"https://dealer.example/x1-used"}}</script>
    <footer>BMW DEMO CARS</footer></body></html>'''
    rows=parse_live_listings(html,"Generic Dealer","https://dealer.example/x1-used")
    assert rows[0]["condition_signal"]=="used"
