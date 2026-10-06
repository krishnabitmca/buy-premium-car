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
