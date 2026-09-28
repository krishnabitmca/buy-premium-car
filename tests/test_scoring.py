from types import SimpleNamespace
from src.scoring import enrich_and_score

def test_bargain():
    v=SimpleNamespace(year_manufacture=2024,mileage_km=12000,price_lakh=32.0,owner_count=1,source_tier=1,certification=None,condition_signal=None,live_verified=True,data_consistent=True,sold_signal=False,comparable_count=0,comparable_median_lakh=None,comparable_low_lakh=None,comparable_high_lakh=None,discount_vs_comparable_pct=None,km_per_year=None,opportunity_score=None,opportunity_class=None,verification_notes=[])
    comps=[{"price_lakh":38.0},{"price_lakh":37.5},{"price_lakh":39.0},{"price_lakh":38.5}]
    settings=SimpleNamespace(market={"reference_date":"2026-09-28","low_mileage_km":20000,"mileage_preference_km":50000,"exceptional_discount_vs_comparables_pct":15,"bargain_discount_vs_comparables_pct":10,"min_comparables_for_price_call":4})
    enrich_and_score(v,comps,settings)
    assert v.discount_vs_comparable_pct>10
    assert v.opportunity_class in {"bargain","exceptional"}
