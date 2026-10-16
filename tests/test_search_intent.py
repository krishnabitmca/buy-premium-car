import pytest
from src.search_intent import SearchIntent, matches_refinements


@pytest.mark.parametrize('body', [
    {'budget_max':'NaN'}, {'budget_min':True}, {'max_mileage_km':-1},
    {'max_owners':1.5}, {'fuels':'petrol'}, {'fuels':['water']},
    {'transmissions':['anything']}, {'sort':'random'}, {'condition':'new'},
    {'budget_min':50,'budget_max':20}, {'query':'x'*161},
    {'query':False}, {'fuels':False},
])
def test_invalid_or_unbounded_constraints_are_rejected(body):
    with pytest.raises(ValueError):
        SearchIntent.parse(body)


def test_destination_is_not_an_inventory_boundary_and_unknowns_fail_closed():
    intent=SearchIntent.parse({'destination':'Bengaluru','fuels':['Petrol'],
                              'transmissions':['automatic'],'max_mileage_km':40000})
    assert matches_refinements({'fuel':'petrol','transmission':'DCT','km':39000,'location':'Delhi'},intent)
    assert not matches_refinements({'fuel':'petrol','transmission':'DCT','km':None},intent)
    assert not matches_refinements({'fuel':'diesel','transmission':'DCT','km':39000},intent)


def test_public_roundtrip_preserves_hard_constraints():
    intent=SearchIntent.parse({'query':'Honda City','budget_max':20,'fuels':['petrol'],
                              'body_types':['sedan'],'max_owners':1,'sort':'km'})
    assert SearchIntent.parse(intent.public()) == intent
