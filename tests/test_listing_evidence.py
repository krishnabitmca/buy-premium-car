import json
from pathlib import Path
import pytest
from src.listing_evidence import structured_evidence,catalogue_tombstones,SameOriginRedirect


URL='https://dealer.example/listing/bmw-x5'


def product(**updates):
    row={'@type':'Car','url':URL,'name':'2024 BMW X5 xDrive40i',
         'offers':{'@type':'Offer','url':URL,'price':'7500000','priceCurrency':'INR','availability':'https://schema.org/InStock'}}
    row.update(updates)
    return '<script type="application/ld+json">'+json.dumps(row)+'</script>'


def test_exact_listing_price_and_explicit_availability():
    assert structured_evidence(product(),URL,'BMW','X5')=={'outcome':'available','price_lakh':75,'availability':'InStock'}
    assert structured_evidence(product(offers={'availability':'https://schema.org/SoldOut'}),URL,'BMW','X5')['outcome']=='unavailable'


@pytest.mark.parametrize('updates',[
    {'url':'https://dealer.example/listing/recommended-car'}, {'name':'BMW X50'},
    {'offers':{'price':7500000,'priceCurrency':'INR'}},
    {'offers':{'price':7500000,'priceCurrency':'USD','availability':'InStock'}},
    {'offers':{'price':'NaN','priceCurrency':'INR','availability':'InStock'}},
    {'offers':{'@type':'AggregateOffer','price':7500000,'priceCurrency':'INR','availability':'InStock'}},
])
def test_ambiguous_or_unrelated_evidence_cannot_renew_offer(updates):
    assert structured_evidence(product(**updates),URL,'BMW','X5')=={'outcome':'inconclusive'}
    assert structured_evidence('<h1>BMW X5 ₹75 lakh</h1><p>Sold cars FAQ</p>',URL,'BMW','X5')=={'outcome':'inconclusive'}


def test_conflicting_prices_fail_closed():
    offers=[{'price':x,'priceCurrency':'INR','availability':'InStock'} for x in [7000000,7500000]]
    assert structured_evidence(product(offers=offers),URL,'BMW','X5')['outcome']=='inconclusive'


def test_sold_dealer_card_has_exact_link_without_retiring_neighbour():
    html=Path('tests/fixtures/dealer_luxuryride_catalog.html').read_text(encoding='utf-8')
    rows=catalogue_tombstones(html,'https://luxuryrideofficial.com/listing-default/','luxuryride_cards')
    assert len(rows)==1 and rows[0]['reason']=='booked'
    assert rows[0]['url'].endswith('/mercedes-benz-c-class-c-220d-5')
    assert not catalogue_tombstones('<p>Sold cars FAQ</p>','https://example.com','luxuryride_cards')


def test_redirect_to_login_or_other_origin_cannot_renew():
    from urllib.request import Request
    with pytest.raises(ValueError,match='approved origin'):
        SameOriginRedirect().redirect_request(Request(URL),None,302,'',{},'https://login.example/')


def test_expiry_policy_caps_used_demo_and_stricter_source_targets(monkeypatch):
    from src.inventory_freshness import expiry_minutes
    monkeypatch.setenv('CARSCANNER_INVENTORY_EXPIRE_MINUTES','10080')
    monkeypatch.setenv('CARSCANNER_USED_EXPIRE_MINUTES','2880')
    monkeypatch.setenv('CARSCANNER_DEMO_EXPIRE_MINUTES','1440')
    assert expiry_minutes('used')==2880
    assert expiry_minutes('demo')==1440
    assert expiry_minutes('used',60)==expiry_minutes('demo',60)==60
