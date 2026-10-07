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
    assert "last_verified_at >= now() - interval '7 days'" in source
    assert "source_count" in source
