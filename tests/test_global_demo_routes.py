"""Global acquisition must exercise real route selection, not mocked targets."""
import pytest

from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter
from src.scan_contract import generation, scan_scope

ROOT='https://www.bmwusedcars.in/buy-used-cars'
DEMO=ROOT+'?models=demo_dealer_cars'


def source(**changes):
    return dict(name='BMW Premium Selection',url=ROOT,adapter_status='live',
                metadata={'brand_demo_query_url_template':DEMO},**changes)


def test_global_demo_uses_explicit_literal_route_and_keeps_endpoint_policies():
    adapter=BuiltinMarketplaceAdapter(source(endpoints=[
        {'url':ROOT}, {'url':ROOT+'?other=demo','condition':'demo'},
        {'url':ROOT+'?used=1','condition':'used'},
        {'url':ROOT+'?disabled=1','is_active':False}]))
    assert adapter._urls(AdapterRequest(query='',condition='demo')) == [DEMO,ROOT+'?other=demo']
    assert adapter._urls(AdapterRequest(query='',condition='both'))[0] == ROOT
    assert adapter._urls(AdapterRequest(query='',condition='used'))[0] == ROOT


@pytest.mark.parametrize('key',['demo_catalog_url','brand_demo_query_url_template','demo_query_url_template'])
def test_global_demo_respects_explicit_condition_route_key(key):
    adapter=BuiltinMarketplaceAdapter(source(**{key:DEMO}))
    assert adapter._urls(AdapterRequest(condition='demo'))[0] == DEMO


@pytest.mark.parametrize('route',[
    'https://unreviewed.invalid/cars','http://www.bmwusedcars.in/buy-used-cars',
    'https://user:password@www.bmwusedcars.in/buy-used-cars',
    ROOT+'/{brand_slug}',ROOT+'?model={model_slug}',ROOT+'#demo',
    'https://[invalid',ROOT+'?bad=two words',ROOT+'?bad=\nvalue'])
def test_unsafe_or_brand_scoped_templates_do_not_become_global_routes(route):
    adapter=BuiltinMarketplaceAdapter(source())
    adapter.source['metadata']={'brand_demo_query_url_template':route}
    assert adapter._urls(AdapterRequest(condition='demo')) == [ROOT]


def test_missing_global_route_keeps_safe_base_without_brand_inference():
    adapter=BuiltinMarketplaceAdapter({'name':'Fixture','url':ROOT,'adapter_status':'live'})
    assert adapter._urls(AdapterRequest(condition='demo')) == [ROOT]


def test_old_generic_root_continuation_restarts_and_does_not_label_used_as_demo(monkeypatch):
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE','1')
    monkeypatch.setattr('src.live_marketplaces._known_brand_names',lambda:['BMW'])
    monkeypatch.setattr('src.source_adapters.adapter_execution_allowed',lambda _:True)
    monkeypatch.setattr('src.source_adapters.record_adapter_execution',lambda *a,**kw:None)
    fetched=[]
    def fetch(url):
        fetched.append(url)
        return '<p>End</p>'
    monkeypatch.setattr('src.source_adapters.fetch_text',fetch)
    monkeypatch.setattr('src.source_adapters.parse_live_listings',lambda *a:[
        {'brand':'BMW','model':'X1','url':ROOT+'/car','price_lakh':30,
         'condition_signal':'used','live_verified':True}])
    monkeypatch.setattr('src.source_adapters.parse_visible_listing_links',lambda *a:[])
    previous={'root_urls':[ROOT],'visited_urls':[ROOT],
        'pending_urls':[ROOT+'?page=2'],'oem_cursors':{ROOT:{'next_group':2}}}
    _,old_fingerprint=scan_scope(source(),AdapterRequest(condition='demo',continuation={}),[ROOT])
    old_generation=generation({},old_fingerprint)
    previous['scan_generation']=old_generation
    result=BuiltinMarketplaceAdapter(source()).fetch(AdapterRequest(condition='demo',continuation=previous))
    assert fetched == [DEMO]
    assert result.status=='live' and result.listings==[]
    assert result.scan_evidence['scope']['roots']==[DEMO]
    assert not result.scan_evidence['resumed_legacy_checkpoint']
    assert result.scan_evidence['generation_id'] != old_generation['generation_id']
    assert not result.scan_evidence['completeness_verified']


def test_global_condition_route_keeps_twelve_endpoint_cap():
    adapter=BuiltinMarketplaceAdapter(source(endpoints=[{'url':ROOT+f'?page={n}'} for n in range(30)]))
    assert len(adapter._urls(AdapterRequest(condition='demo'))) == 12
