import pytest

from src.reviewed_inventory import parse_quikr_cards
from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter


HTML='''
<a class="qc-ads__card" href="/cars/used-white-2019-hyundai-creta-in-whitefield-bangalore/p/375941747">
 <figure><img data-src="https://teja8.kuikr.com/i5/creta.jpeg" alt="Hyundai Creta SX PETROL MT - 2019"></figure>
 <div class="qc-ads__card--body footerSection" data-ad-object='{"ad_id":375941747,"properties":{"seller_type":"C2C"}}'>
  <h2>Hyundai Creta SX PETROL MT - 2019</h2>
  <div class="prime-features">63,833 kms / Petrol / 1st Owner</div><div class="price">₹9,73,000</div>
 </div><footer class="qc-ads__card--footer"><p><label>Location:</label><span>Bangalore</span></p></footer>
</a>
<a class="qc-ads__card" href="/cars/used-black-2018-bmw-x1-in-delhi/p/987654321">
 <img src="https://teja9.kuikr.com/i5/x1.jpeg"><div class="qc-ads__card--body" data-ad-object='{"ad_id":987654321}'>
  <h2>BMW X1 sDrive20d Expedition - 2018</h2><div class="prime-features">57,000 kms / Diesel / 2nd Owner</div>
  <div class="price">₹17,95,000</div></div><footer class="qc-ads__card--footer"><span>Delhi</span></footer>
</a>'''


def test_quikr_cards_preserve_ad_identity_and_evidence():
    rows=parse_quikr_cards(HTML,'Quikr Cars','https://www.quikr.com/cars/used+cars+all-india+z1399')
    assert len(rows)==2
    creta=next(row for row in rows if row['brand']=='Hyundai')
    assert creta['source_listing_id']=='375941747'
    assert creta['model']=='Creta SX PETROL MT'
    assert creta['price_lakh']==9.73 and creta['km']==63833
    assert creta['owners']==1 and creta['fuel']=='Petrol' and creta['location']=='Bangalore'
    assert creta['url'].endswith('/p/375941747')
    assert creta['images']==['https://teja8.kuikr.com/i5/creta.jpeg']


def test_quikr_query_filters_and_invalid_cards_fail_closed():
    rows=parse_quikr_cards(HTML,'Quikr Cars','https://www.quikr.com/cars/used+cars+all-india+z1399','BMW X1')
    assert [row['source_listing_id'] for row in rows]==['987654321']
    bad=HTML.replace('/p/375941747','/p/111').replace('/p/987654321','/p/222')
    with pytest.raises(ValueError,match='no valid evidence'):
        parse_quikr_cards(bad,'Quikr Cars','https://www.quikr.com/cars/used+cars+all-india+z1399')


def test_quikr_rejects_unsafe_host_image_and_unknown_brand():
    html=HTML.replace('https://teja8.kuikr.com/i5/creta.jpeg','https://tracker.invalid/car.jpeg')
    rows=parse_quikr_cards(html,'Quikr Cars','https://www.quikr.com/cars/used+cars+all-india+z1399')
    assert next(row for row in rows if row['brand']=='Hyundai')['images']==[]
    unknown=HTML.replace('Hyundai Creta SX PETROL MT','Unknown Creta').replace('BMW X1 sDrive20d Expedition','Unknown X1')
    with pytest.raises(ValueError,match='no valid evidence'):
        parse_quikr_cards(unknown,'Quikr Cars','https://www.quikr.com/cars/used+cars+all-india+z1399')
    with pytest.raises(ValueError,match='Unreviewed Quikr host'):
        parse_quikr_cards(HTML,'Quikr Cars','https://example.com/cars/')


def test_quikr_empty_catalogue_does_not_use_generic_fallback(monkeypatch):
    source={'name':'Quikr Cars','url':'https://www.quikr.com/cars/used+cars+all-india+z1399',
            'adapter_status':'live','parser_strategy':'quikr_cards'}
    monkeypatch.setattr('src.source_adapters.fetch_text',lambda _url:'<html><body>No offers</body></html>')
    monkeypatch.setattr('src.source_adapters.parse_live_listings',lambda *_args:[{'source':'wrong'}])
    monkeypatch.setattr('src.source_adapters.parse_visible_listing_links',lambda *_args:[{'source':'wrong'}])
    result=BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(query='',condition='used'))
    assert result.status=='live' and result.listings==[]
