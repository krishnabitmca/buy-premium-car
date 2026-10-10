import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from api.search import _match, _vehicle_condition
from src.inventory_contract import json_inventory_value


def test_database_types_remain_usable_by_legacy_web_client():
    vehicle_id=uuid4()
    observed=datetime(2026,10,10,12,tzinfo=timezone(timedelta(hours=5,minutes=30)))
    row={"vehicle_id":vehicle_id,"price_lakh":Decimal("30.25"),
         "identity_confidence":Decimal("0.9"),"observed_at":observed,
         "offers":[{"price_lakh":Decimal("31.25"),"last_verified_at":observed}]}
    result=json.loads(json.dumps(json_inventory_value(row),allow_nan=False))
    assert result["vehicle_id"]==str(vehicle_id)
    assert result["price_lakh"]==30.25
    assert isinstance(result["price_lakh"],float)
    assert result["observed_at"]=="2026-10-10T06:30:00+00:00"
    assert result["offers"][0]["price_lakh"]==31.25
    assert result["offers"][0]["last_verified_at"]==result["observed_at"]
    assert row["observed_at"] is observed


@pytest.mark.parametrize("value",[Decimal('NaN'),Decimal('Infinity'),Decimal('-Infinity')])
def test_invalid_database_numbers_are_rejected(value):
    with pytest.raises(ValueError,match='finite'):
        json_inventory_value({"price_lakh":value})


def test_naive_timestamp_is_not_silently_assigned_a_timezone():
    with pytest.raises(ValueError,match='timezone'):
        json_inventory_value(datetime(2026,10,10))


def test_unexpected_types_are_not_silently_stringified():
    with pytest.raises(TypeError):
        json.dumps(json_inventory_value({"unexpected":object()}))


@pytest.mark.parametrize('condition',['used','demo'])
def test_inventory_condition_is_accepted_by_final_search_filter(condition):
    row={"condition":condition,"price_lakh":30}
    assert _vehicle_condition(row)==condition
    assert _match(row,'',20,40,None,'Bengaluru',condition)
    opposite='demo' if condition=='used' else 'used'
    assert not _match(row,'',20,40,None,'Bengaluru',opposite)


def test_explicit_unknown_condition_is_not_overridden_by_fallback():
    assert _vehicle_condition({'condition_signal':'unknown','condition':'demo'})=='unknown'
