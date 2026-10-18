from copy import deepcopy
from datetime import datetime,timezone,timedelta
import pytest
from src.coverage_benchmark import evaluate_sample,url_key

NOW=datetime(2026,10,18,17,tzinfo=timezone.utc)


def sample():
    return {'version':1,'sampling':{'method':'manual_source_review','reviewer':'reviewer-fixture',
            'scope':'Synthetic test sample, not real coverage evidence','collected_at':NOW.isoformat()},
            'records':[{'source':'Dealer','brand':'BMW','model':'X1','seller_state':'Delhi',
                        'condition':'used','eligible':True,'url':'https://fixture.invalid/car?id=1&utm_source=test'}]}


def test_sample_recall_uses_source_listing_identity_not_brand_presence_or_duplicate_offers():
    data=sample()
    data['records'].append({**data['records'][0],'url':'https://fixture.invalid/car?id=2','condition':'demo'})
    offer={'source':'Dealer','brand':'BMW','model':'X1','condition':'used','url':'https://fixture.invalid/car?id=1'}
    result=evaluate_sample(data,[offer,offer],now=NOW)
    assert result['eligible_sample']==2 and result['matched']==1 and result['sample_recall']==.5
    assert len(result['gaps'])==1 and result['gaps'][0]['condition']=='demo'
    assert not result['national_coverage_established']
    assert result['independence']=='collector_attested_not_machine_verified'


def test_price_page_query_identifiers_are_preserved_and_mismatched_facts_do_not_count():
    assert url_key('https://fixture.invalid/car?id=1')!=url_key('https://fixture.invalid/car?id=2')
    assert url_key('https://fixture.invalid/car?id=1#photo')==url_key('https://fixture.invalid/car?id=1&utm_source=x')
    result=evaluate_sample(sample(),[{'source':'Dealer','brand':'BMW','model':'X3','condition':'used',
                              'url':'https://fixture.invalid/car?id=1'}],now=NOW)
    assert result['matched']==0 and result['gaps'][0]['status']=='attribute_mismatch'


@pytest.mark.parametrize('change', ['export','old','future','naive','duplicate','missing_label'])
def test_benchmark_rejects_unreliable_samples(change):
    data=sample()
    if change=='export':data['sampling']['method']='inventory_export'
    elif change=='old':data['sampling']['collected_at']=(NOW-timedelta(days=2)).isoformat()
    elif change=='future':data['sampling']['collected_at']=(NOW+timedelta(seconds=1)).isoformat()
    elif change=='naive':data['sampling']['collected_at']=NOW.replace(tzinfo=None).isoformat()
    elif change=='duplicate':data['records'].append(deepcopy(data['records'][0]))
    elif change=='missing_label':data['records'][0]['eligible']='true'
    with pytest.raises(ValueError):evaluate_sample(data,[],now=NOW)


def test_all_excluded_labels_produce_no_recall_claim():
    data=sample();data['records'][0]['eligible']=False
    result=evaluate_sample(data,[],now=NOW)
    assert result['eligible_sample']==0 and result['sample_recall'] is None


def test_source_reviewed_sold_label_detects_unexpectedly_searchable_offer():
    data=sample();data['records'][0]['eligible']=False
    offer={'source':'Dealer','brand':'BMW','model':'X1','condition':'used','url':data['records'][0]['url']}
    result=evaluate_sample(data,[offer],now=NOW)
    assert result['ineligible_indexed_count']==1
    assert result['ineligible_indexed'][0]['status']=='unexpectedly_eligible'
