from src.car_watch import watch_to_intent
from src.deal_engine import DealIntent

def test_watch_to_intent_keeps_user_criteria_generic():
    watch={
        "watch_id":"w1","natural_language_request":"BMW X3",
        "target_discount_pct":10,"alert_quality":"good",
        "constraints":{
            "budget_min_lakh":25,"budget_max_lakh":45,
            "min_age_years":2,"max_age_years":6,
            "make":"BMW","model":"X3","condition":"used_demo",
            "mileage_max_km":50000,"max_owners":2,"location":"Pune","radius_km":250,
        }
    }
    intent=watch_to_intent(watch)
    assert isinstance(intent,DealIntent)
    assert intent.budget_min==25 and intent.budget_max==45
    assert intent.min_age_years==2 and intent.max_age_years==6
    assert intent.location=="Pune" and intent.radius_km==250
    assert intent.must_have["intent_make"]=="BMW"
