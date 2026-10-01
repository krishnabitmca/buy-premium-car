from src.acquisition import purchase_context
from src.india_geo import infer_city, infer_state


def test_bengaluru_is_destination_state():
    assert infer_state("Bengaluru", "Bengaluru") == "Karnataka"
    assert infer_city("Bangalore", "Bangalore") == "Bengaluru"


def test_interstate_purchase_is_context_not_search_boundary():
    vehicle = {"location": "Hyderabad", "price_lakh": 37.5}
    ctx = purchase_context(vehicle, "Bengaluru")
    assert ctx["destination_state"] == "Karnataka"
    assert ctx["seller_state"] == "Telangana"
    assert ctx["mode"] == "interstate"
    assert ctx["observed_listing_price_lakh"] is None
    assert "interstate" in ctx["note"].lower()


def test_same_state_purchase_context():
    vehicle = {"location": "Bengaluru", "price_lakh": 39.5}
    ctx = purchase_context(vehicle, "Bengaluru")
    assert ctx["mode"] in {"local", "same_state"}
    assert ctx["estimated_total_lakh"] == 39.5
