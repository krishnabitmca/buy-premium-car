import io
import json
from pathlib import Path
from urllib.parse import parse_qs
import pytest
from src.reviewed_inventory import parse_reviewed_cards,fetch_skoda_inventory,reviewed_detail_evidence
from src.source_adapters import BuiltinMarketplaceAdapter,AdapterRequest
from src.listing_evidence import catalogue_tombstones

ROOT=Path('tests/fixtures')
SKODA='https://www.skodapreowned.in/buy'
FUSION='https://fusioncars.in/brand/mercedes-benz/'


def fixture(name):return (ROOT/('reviewed_'+name)).read_text(encoding='utf-8')


@pytest.fixture(autouse=True)
def identity(monkeypatch):
    monkeypatch.setattr('src.live_marketplaces._known_brand_names',lambda:['BMW','Mercedes-Benz','Skoda','Honda','Hyundai','Mahindra'])


def test_fusion_card_prices_registration_unknown_location_and_explicit_sold():
    rows=parse_reviewed_cards(fixture('fusion.html'),'Fusion',FUSION,'fusion_cards')
    assert len(rows)==3 and [r['price_lakh'] for r in rows[:2]]==[210,51]
    assert rows[1]['model']=='E-Class' and rows[1]['registration_year']==2022
    assert rows[0]['mfg_year'] is None and rows[0]['location'] is None
    assert all(r['condition_signal']=='used' and r['source_listing_id'] and r['images'] for r in rows)
    assert 'UNREGISTERED' in rows[-1]['listing_name'] and rows[-1]['registration_year'] is None
    assert len(catalogue_tombstones(fixture('fusion.html'),FUSION,'fusion_cards'))==1


def test_skoda_preserves_individual_ids_unknown_mileage_and_range_is_not_manufacture_year():
    rows=parse_reviewed_cards(fixture('skoda.html'),'Skoda OEM',SKODA,'skoda_cards')
    assert len(rows)==2 and rows[0]['price_lakh']==15.1
    assert rows[0]['brand']=='Skoda' and rows[0]['model']=='KUSHAQ'
    assert rows[0]['km'] is None and rows[0]['mfg_year'] is None
    assert rows[0]['location']=='GURGAON' and rows[0]['owners']==1
    assert rows[0]['source_listing_id']=='209538'


def test_reviewed_stock_uses_shared_brand_aliases_instead_of_dropping_mg(monkeypatch):
    monkeypatch.setattr('src.live_marketplaces._known_brand_names',lambda:['MG Motor'])
    body=fixture('skoda.html').replace('SKODA','MG').replace('KUSHAQ','HECTOR').replace('KYLAQ','ASTOR')
    rows=parse_reviewed_cards(body,'OEM',SKODA,'skoda_cards')
    assert len(rows)==2 and all(row['brand']=='MG Motor' for row in rows)


@pytest.mark.parametrize('name,strategy,url',[('fusion.html','fusion_cards',FUSION),('skoda.html','skoda_cards',SKODA)])
def test_duplicate_cards_external_links_and_missing_price_never_create_extra_stock(name,strategy,url):
    body=fixture(name);rows=parse_reviewed_cards(body,'S',url,strategy)
    assert parse_reviewed_cards(body+body,'S',url,strategy)==rows
    assert not parse_reviewed_cards(body.replace(url.split('/')[2],'unreviewed.invalid'),'S',url,strategy)
    assert not parse_reviewed_cards('<h1>Used demo car ₹20 lakh</h1>','S',url,strategy)
    assert not parse_reviewed_cards(body,'S',url,strategy,'Honda City')


class FakeOpener:
    def __init__(self,second=None):self.calls=[];self.second=second or fixture('skoda_page2.json')
    def open(self,request,timeout):
        self.calls.append(request)
        body=fixture('skoda.html') if request.data is None else json.dumps({'stock':fixture('skoda.html')}) if parse_qs(request.data.decode())['move_page']==['1'] else self.second
        return io.BytesIO(body.encode())


def test_oem_resumes_advertised_pages_with_fresh_ephemeral_session_and_shared_budget():
    first=fetch_skoda_inventory(SKODA,'OEM',page_budget=1,opener=FakeOpener())
    assert first.pages_fetched==1 and first.continuation=={'next_page':2}
    opener=FakeOpener();second=fetch_skoda_inventory(SKODA,'OEM',continuation=first.continuation,page_budget=1,opener=opener)
    assert second.continuation=={'next_page':3} and second.pages_fetched==1
    assert second.listings[0]['url']!=first.listings[0]['url']
    assert len(opener.calls)==2 and opener.calls[1].full_url=='https://www.skodapreowned.in/buySearch'
    fields=parse_qs(opener.calls[1].data.decode())
    assert fields['move_page']==['2'] and fields['_token']==['fixture-token']
    assert 'token' not in str(second.continuation)


def test_wrong_page_or_missing_pagination_fails_instead_of_completing_empty():
    second=fixture('skoda_page2.json').replace('data-page=\\"2\\"','data-page=\\"1\\"')
    with pytest.raises(ValueError,match='pagination'):
        fetch_skoda_inventory(SKODA,'OEM',continuation={'next_page':2},page_budget=1,opener=FakeOpener(second))
    with pytest.raises(ValueError):fetch_skoda_inventory('https://unreviewed.invalid','OEM')


def test_fusion_advertised_brand_catalogues_share_durable_frontier(monkeypatch):
    monkeypatch.setattr('src.source_adapters.fetch_text',lambda url:'<a href="/brand/mercedes-benz/">Mercedes stock</a>' if url.endswith('/collections/') else fixture('fusion.html'))
    monkeypatch.setattr('src.source_adapters.adapter_execution_allowed',lambda _:True)
    monkeypatch.setattr('src.source_adapters.record_adapter_execution',lambda *a,**kw:None)
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE','1')
    source={'name':'Fusion','url':'https://fusioncars.in/collections/','parser_strategy':'fusion_cards','catalogue_link_pattern':r'/brand/[a-z0-9-]+/?'}
    adapter=BuiltinMarketplaceAdapter(source)
    first=adapter.fetch(AdapterRequest(continuation={}))
    assert first.status=='live' and first.continuation['pending_urls']==[FUSION.rstrip('/')]
    second=adapter.fetch(AdapterRequest(continuation=first.continuation))
    assert len(second.listings)==3 and second.pages_fetched==1 and second.tombstones
    assert not adapter.fetch(AdapterRequest(condition='demo',continuation=first.continuation)).listings


@pytest.mark.parametrize('name,url,brand,model,price',[
    ('fusion_detail.html','https://fusioncars.in/cars/2021-22-mercedes-benz-e-200/','Mercedes-Benz','E-Class',51),
    ('skoda_detail.html','https://www.skodapreowned.in/car-details/209538','Skoda','KUSHAQ',15.1)])
def test_individual_renewal_ignores_faq_related_prices_and_rejects_wrong_vehicle(name,url,brand,model,price):
    body=fixture(name)
    assert reviewed_detail_evidence(body,url,brand,model)['price_lakh']==price
    assert reviewed_detail_evidence(body,url,brand,'Wrong Model')['outcome']=='inconclusive'
    assert reviewed_detail_evidence(body,url,brand,model,'demo')['outcome']=='condition_unverified'
    assert reviewed_detail_evidence('<h1>Used '+brand+' '+model+' ₹1 lakh</h1>',url,brand,model)['outcome']=='inconclusive'
    assert reviewed_detail_evidence(body.replace('209538','999999').replace('e-200/','wrong-car/'),url,brand,model)['outcome']=='inconclusive'


def test_related_car_sold_badges_cannot_retire_the_identified_vehicle():
    body=fixture('fusion_detail.html');url='https://fusioncars.in/cars/2021-22-mercedes-benz-e-200/'
    related='<div class="similar_lg"><a href="/cars/unrelated/"><div class="my-badge">Sold</div></a></div>'
    assert reviewed_detail_evidence(body+related,url,'Mercedes-Benz','E-Class')['outcome']=='available'
    assert reviewed_detail_evidence(body+related.replace('/cars/unrelated/',url),url,'Mercedes-Benz','E-Class')['outcome']=='unavailable'


def test_rollout_checks_all_selected_sources_before_any_registry_write(monkeypatch,tmp_path):
    from scripts import enable_reviewed_feeds as rollout
    from src.source_adapters import AdapterResult
    row=parse_reviewed_cards(fixture('skoda.html'),'OEM',SKODA,'skoda_cards')[0]
    writes=[]
    class Probe:
        def __init__(self,source):self.source=source
        def fetch(self,request):
            return AdapterResult(self.source['name'],[row,row],status='live' if 'Skoda' in self.source['name'] else 'unavailable')
    monkeypatch.setattr(rollout,'BuiltinMarketplaceAdapter',Probe)
    monkeypatch.setattr(rollout,'fetch_listing',lambda _:fixture('skoda_detail.html'))
    monkeypatch.setattr(rollout,'sync_registry',lambda sources:writes.append(sources))
    monkeypatch.setattr('sys.argv',['rollout','--source','Skoda Certified Pre-Owned','--source','Fusion Cars','--apply','--report',str(tmp_path/'report.json')])
    with pytest.raises(RuntimeError,match='stock verification'):
        rollout.main()
    assert writes==[]
