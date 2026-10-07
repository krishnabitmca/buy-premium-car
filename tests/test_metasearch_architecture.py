from src.canonical_identity import candidate_identity
from src.models import Vehicle


def _v(source, url, **kwargs):
    data=dict(brand="BMW",model="X1",year_manufacture=2025,mileage_km=3200,
              variant="sDrive18i M Sport",fuel="petrol",transmission="automatic",
              seller_city="Bengaluru",registration_state="KA")
    data.update(kwargs)
    return Vehicle(source_name=source,source_tier=2,url=url,title="BMW X1",**data)


def test_same_physical_vehicle_gets_source_agnostic_candidate_identity():
    a,ca,ea=candidate_identity(_v("OEM","https://oem/a"))
    b,cb,eb=candidate_identity(_v("Marketplace","https://market/b"))
    assert a == b
    assert a.startswith("candidate:")
    assert ca >= .8 and cb >= .8
    assert ea["mode"] == "candidate"


def test_materially_different_mileage_does_not_share_candidate_identity():
    a,_,_=candidate_identity(_v("OEM","https://oem/a"))
    b,_,_=candidate_identity(_v("Marketplace","https://market/b",mileage_km=9200))
    assert a != b


def test_weak_evidence_stays_provisional():
    v=Vehicle(source_name="A",source_tier=2,url="https://a/x",title="BMW X1",brand="BMW",model="X1")
    key,confidence,evidence=candidate_identity(v)
    assert key is None
    assert confidence == 0
    assert evidence["mode"] == "provisional"


def test_inventory_query_exposes_multi_provider_offers_and_freshness_gate():
    source=open("src/inventory_db.py").read()
    assert "jsonb_agg(jsonb_build_object" in source
    assert '"offers"' in source
    assert "CARSCANNER_INVENTORY_EXPIRE_MINUTES" in source
    assert "make_interval(mins => %s)" in source
    assert "source_count" in source


def test_search_api_exposes_marketplace_diagnostics_and_offer_aware_source_count():
    source=open("api/search.py").read()
    assert '"search_diagnostics"' in source
    assert '"planned_sources"' in source
    assert '"responding_sources"' in source
    assert '"zero_result"' in source
    assert '"zero_result_reason"' in source
    assert 'v.get("offers")' in source


def test_search_ranking_rewards_provider_choice_and_completeness():
    from api.search import _score
    base={"discount_pct":5,"identity_confidence":.9,"live_verified":True,"data_consistent":True,
          "km":10000,"owners":1,"source_count":1}
    richer=dict(base,source_count=3,image_urls=["https://img.example/car.jpg"],observed_at="2026-10-07T00:00:00Z")
    assert _score(richer) > _score(base)


def test_vin_is_authoritative_across_sources():
    a,ca,ea=candidate_identity(_v("OEM","https://oem/a",vin="WBA12345678901234"))
    b,cb,eb=candidate_identity(_v("Marketplace","https://market/b",vin="wba-12345678901234",mileage_km=9900))
    assert a == b == "vin:wba12345678901234"
    assert ca == cb == 1.0
    assert ea["mode"] == eb["mode"] == "vin"


def test_search_score_rewards_a_real_comparable_discount():
    from api.search import _score
    common={"identity_confidence":.9,"live_verified":True,"data_consistent":True,
            "km":10000,"owners":1,"source_count":2,"observed_at":"2026-10-07T00:00:00Z"}
    assert _score(dict(common,discount_pct=10)) > _score(dict(common,discount_pct=0))


def test_search_computes_score_after_discount_enrichment():
    source=open("api/search.py").read()
    discount_pos=source.index('v["discount_pct"]=round')
    score_pos=source.index('v["_search_score"]=_score(v)')
    assert score_pos > discount_pos


def test_zero_result_reason_is_actionable():
    from api.search import _zero_result_reason
    assert _zero_result_reason(result_count=0,source_plan=[],sources=[],search_mode="live",availability_warning=None) == "no_eligible_sources"
    assert _zero_result_reason(result_count=0,source_plan=[{"name":"A"}],sources=[],search_mode="live_fallback",availability_warning=None) == "sources_unavailable"
    assert _zero_result_reason(result_count=0,source_plan=[{"name":"A"}],sources=[{"name":"A","status":"live"}],search_mode="live",availability_warning=None) == "no_matching_inventory"
    assert _zero_result_reason(result_count=1,source_plan=[],sources=[],search_mode="live",availability_warning=None) is None


def test_inventory_ingestion_serializes_jsonb_payloads():
    source=open("src/inventory_ingestion.py").read()
    assert "json.dumps(evidence)" in source
    assert '"vin":v.vin' in source
