from dataclasses import replace
import pytest
from src.models import Vehicle
from src.canonical_identity import candidate_identity, normalized_full_vin


def car(**kwargs):
    return Vehicle(source_name='Dealer A', source_tier=1, url='https://fixture.invalid/stock/1',
                   title='BMW X1', brand='BMW', model='X1', year_manufacture=2024,
                   mileage_km=10000, fuel='petrol', transmission='automatic', **kwargs)


@pytest.mark.parametrize('value', ['12345678', 'WBA1234567890123', 'WBA123456789012345',
    'WBA12345*78901234', 'WBA12345?78901234', 'WBA12345-78901234',
    'WBA12345I78901234', 'WBA12345O78901234', 'WBA12345Q78901234',
    'XXXXXXXXXXXXXXXXX', '00000000000000000', '12345678901234567', 'WBA123XXXX8901234'])
def test_partial_masked_invalid_identifiers_never_confirm_or_use_shared_attribute_key(value):
    assert normalized_full_vin(value) is None
    for field in ('vin', 'chassis_number'):
        key, confidence, evidence = candidate_identity(car(**{field: value}))
        assert key is None and confidence == 0
        assert evidence['mode'] == 'provisional'
        assert evidence['reason'] == 'unsupported_or_partial_identifier'


def test_full_case_normalized_vin_has_provenance_without_claiming_physical_verification():
    first = car(vin=' WBA12345678901234 ')
    second = replace(first, source_name='Dealer B', vin=None,
                     metadata={'vehicle_identification_number': 'wba12345678901234'})
    assert candidate_identity(first)[0] == candidate_identity(second)[0] == 'vin:wba12345678901234'
    assert candidate_identity(second)[2]['identifier_fields'] == ['metadata.vehicle_identification_number']
    assert candidate_identity(first)[2]['validation'] == 'format_only'
    assert candidate_identity(first)[2]['physical_identity_verified'] is False


def test_conflicting_full_identifiers_are_not_resolved_by_field_order():
    for item in (car(vin='WBA12345678901234', chassis_number='WBA12345678901235'),
                 car(vin='WBA12345678901234', metadata={'vin': 'WBA12345678901235'})):
        key, confidence, evidence = candidate_identity(item)
        assert key is None and confidence == 0
        assert evidence['mode'] == 'conflict'
        assert evidence['reason'] == 'conflicting_full_identifiers'


def test_no_identifier_retains_explicit_candidate_contract():
    key, confidence, evidence = candidate_identity(car())
    assert key.startswith('candidate:') and confidence < 1
    assert evidence['mode'] == 'candidate'


def test_legacy_identity_audit_is_explicit_about_review_and_redacts_identifier():
    from src.identity_audit import assess_record
    row={'vehicle_id':'fixture-id','identity_key':'vin:partial1234','identity_state':'confirmed',
         'identity_evidence':{'mode':'vin'},'listing_count':2,'source_count':2}
    result=assess_record(row)
    assert result['reasons']==['legacy_invalid_full_vin','legacy_confirmation_requires_review']
    assert 'partial1234' not in str(result)
    assert result['source_count']==2
    row.update(identity_key='vin:wba12345678901234',identity_evidence={'identity_policy':'full-vin-v1'})
    assert assess_record(row) is None
