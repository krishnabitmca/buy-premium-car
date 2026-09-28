from src.deal_engine import DealIntent, GenericDealEngine, ListingSnapshot, live_listing

def test_generic_engine_reaches_high_priority_for_real_deal():
    intent = DealIntent(intent_id="i1", category="electronics", query="premium laptop", budget_max=100000,
                        must_have={"ram_gb": 32}, nice_to_have={"storage_gb": [512, 1024], "display": "oled"},
                        target_discount_pct=10, notification_channels=("email", "whatsapp"))
    listing = ListingSnapshot(listing_id="l1", category="electronics", title="Laptop", price=85000,
                              source_trust=0.9, availability="live",
                              attributes={"ram_gb": 32, "storage_gb": 1024, "display": "oled"},
                              fair_value=100000, url="https://example.com/l1")
    result = GenericDealEngine([live_listing]).evaluate(intent, listing)
    assert result.eligible and result.deal_score == 60.0 and result.confidence >= 0.8
    assert result.alert_priority == "high"
    assert GenericDealEngine([live_listing]).should_alert(result)

def test_budget_is_hard_constraint():
    intent = DealIntent(intent_id="i1", category="electronics", query="laptop", budget_max=100000, must_have={"ram_gb": 32})
    listing = ListingSnapshot(listing_id="l2", category="electronics", title="Laptop", price=125000,
                              attributes={"ram_gb": 32}, fair_value=140000, availability="live")
    result = GenericDealEngine([live_listing]).evaluate(intent, listing)
    assert not result.eligible
    assert any("price exceeds budget" in x for x in result.risks)

def test_unavailable_never_alerts():
    intent = DealIntent(intent_id="i1", category="electronics", query="laptop", budget_max=100000)
    listing = ListingSnapshot(listing_id="l3", category="electronics", title="Laptop", price=80000,
                              fair_value=100000, availability="sold")
    engine = GenericDealEngine([live_listing])
    result = engine.evaluate(intent, listing)
    assert not result.eligible and not engine.should_alert(result)

def test_same_engine_supports_automotive():
    intent = DealIntent(intent_id="c1", category="automotive", query="BMW 3 Series", budget_max=4000000)
    listing = ListingSnapshot(listing_id="c1l1", category="automotive", title="BMW 3 Series", price=3600000,
                              fair_value=4000000, availability="live")
    result = GenericDealEngine([live_listing]).evaluate(intent, listing)
    assert result.eligible and result.deal_score == 40.0
