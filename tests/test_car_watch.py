from src.car_watch import watch_to_intent
from src.deal_engine import DealIntent
from src.car_watch import evaluate_watch, listing_to_snapshot
from datetime import datetime, timedelta, timezone
import pytest

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
    assert intent.budget_min==2500000 and intent.budget_max==4500000
    assert intent.min_age_years==2 and intent.max_age_years==6
    assert intent.location=="Pune" and intent.radius_km==250
    assert intent.must_have["make"]=="bmw"
    assert intent.max_mileage_km==50000 and intent.max_owners==2


def watch(**changes):
    value={'watch_id':'watch-1','alert_quality':'any','constraints':{
        'make':'BMW','model':'X3','condition':'both','budget_min_lakh':25,'budget_max_lakh':45,
        'mileage_max_km':50000,'max_owners':2}}
    value.update(changes)
    return value


def listing(**changes):
    value={'vehicle_id':'vehicle-1','listing_id':'offer-1','brand':'BMW','model':'X3',
           'price_lakh':30,'mfg_year':2023,'condition_signal':'used','km':20000,'owners':1,
           'source':'Fixture Dealer','source_tier':1,'url':'https://fixture.invalid/car/1',
           'live_verified':True,'data_consistent':True,'observed_at':datetime.now(timezone.utc).isoformat()}
    value.update(changes)
    return value


def test_any_watch_accepts_verified_budget_match_without_fabricating_deal():
    matches=evaluate_watch(watch(),[listing()])
    assert len(matches)==1
    assert matches[0][1].listing_id=='vehicle-1' and matches[0][1].deal_score==0
    assert listing_to_snapshot(listing()).price==3000000


@pytest.mark.parametrize('changes',[
    {'price_lakh':50},{'price_lakh':20},{'price_lakh':0},{'brand':'Audi'},
    {'model':'X1'},{'brand':None},{'km':60000},{'km':None},{'owners':3},{'owners':None},
    {'condition_signal':'unknown'},{'live_verified':False},{'sold_signal':True},
    {'data_consistent':False},{'observed_at':''},{'observed_at':'invalid'},
    {'observed_at':(datetime.now(timezone.utc)-timedelta(days=30)).isoformat()},
])
def test_hard_constraints_and_current_evidence_reject_invalid_matches(changes):
    assert evaluate_watch(watch(),[listing(**changes)])==[]


def test_condition_uses_explicit_evidence_instead_of_source_or_title_guess():
    demo=watch(constraints={'make':'BMW','model':'X3','condition':'demo'})
    assert len(evaluate_watch(demo,[listing(condition_signal='demo',title='BMW X3')]))==1
    assert evaluate_watch(demo,[listing(condition_signal='used',title='DEMO BMW X3')])==[]


def test_zero_mileage_and_zero_owner_count_remain_known():
    snapshot=listing_to_snapshot(listing(km=0,owners=0))
    assert snapshot.attributes['mileage_km']==0 and snapshot.attributes['owner_count']==0
    assert len(evaluate_watch(watch(),[listing(km=0,owners=0)]))==1


def test_discount_alert_requires_comparison_and_target_gap():
    target=watch(target_discount_pct=10)
    assert evaluate_watch(target,[listing()])==[]
    assert evaluate_watch(target,[listing(comp_median=32)])==[]
    assert len(evaluate_watch(target,[listing(comp_median=40)]))==1
    assert evaluate_watch(watch(alert_quality='good'),[listing()])==[]
    assert len(evaluate_watch(watch(alert_quality='exceptional'),[listing(comp_median=40)]))==1


def test_explicit_radius_fails_closed_without_measured_distance():
    criteria=watch(constraints={'make':'BMW','radius_km':100,'location':'Pune'})
    assert evaluate_watch(criteria,[listing(location='Pune')])==[]
    assert len(evaluate_watch(criteria,[listing(location='Mumbai',distance_km=80)]))==1
    assert evaluate_watch(criteria,[listing(distance_km=120)])==[]


def test_no_location_constraint_keeps_out_of_city_results():
    assert len(evaluate_watch(watch(),[listing(location='Delhi')]))==1
