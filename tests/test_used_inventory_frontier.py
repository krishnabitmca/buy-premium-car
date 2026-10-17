from src.used_inventory_frontier import discover_models
from src import live_marketplaces as lm


def test_used_model_links_include_discontinued_models_and_reject_other_scopes(monkeypatch):
    monkeypatch.setattr(lm,'_known_brand_names',lambda:['Tata','Honda'])
    html='''<a href="/used/tata-nano/">Tata Nano</a>
    <a href="/used/tata-nexon/">2,030 Used Nexon</a>
    <a href="https://evil.example/used/tata-tiago/">Used Tiago</a>
    <a href="/used/honda-city/">Used Honda City</a>
    <a href="/used/tata/page-2/">Next</a>
    <a href="/used/delhi/tata-nano/">Delhi</a>
    <a href="/new/tata-punch/">Punch</a>'''
    rows=discover_models(html,{'parser_strategy':'carwale_cards'},'https://www.carwale.com/used/tata/','Tata',[])
    assert [(r['model'],r['advertised_count']) for r in rows]==[('nano',None),('nexon',2030)]
    assert rows[0]['evidence_url']=='https://www.carwale.com/used/tata-nano/'


def test_observed_cardekho_model_family_is_used_without_carwale_variant_fanout(monkeypatch):
    monkeypatch.setattr(lm,'_known_brand_names',lambda:['Ford','Honda'])
    rows=[{'brand':'Ford','model':'Figo','url':'https://source.example/used-car/1'},
          {'brand':'Honda','model':'City','url':'https://source.example/used-car/2'}]
    assert discover_models('',{'parser_strategy':'cardekho_cards'},'https://source.example','Ford',rows)==[
        {'model':'Figo','evidence_url':'https://source.example/used-car/1','discovery_kind':'observed_model'}]
    assert discover_models('',{'parser_strategy':'carwale_cards'},'https://source.example','Ford',rows)==[]


def test_model_scan_advances_pages_without_revisiting_generic_source_root(monkeypatch):
    from src.source_adapters import BuiltinMarketplaceAdapter,AdapterRequest
    monkeypatch.setattr(lm,'_known_brand_names',lambda:['Tata'])
    monkeypatch.setattr('src.source_adapters.adapter_execution_allowed',lambda _:True)
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE','1')
    source={'name':'Test','url':'https://source.example/used/','adapter_status':'live',
        'parser_strategy':'carwale_cards','brands':['all'],
        'query_url_template':'https://source.example/used/{brand_slug}-{model_slug}/',
        'endpoints':[{'url':'https://source.example/used/'}]}
    calls=[]
    def fetch(url):
        calls.append(url)
        return '<link rel="next" href="/used/tata-altroz/page-2/">' if 'page-2' not in url else '<html></html>'
    monkeypatch.setattr('src.source_adapters.fetch_text',fetch)
    adapter=BuiltinMarketplaceAdapter(source)
    first=adapter.fetch(AdapterRequest(query='Tata Altroz',continuation={}))
    second=adapter.fetch(AdapterRequest(query='Tata Altroz',continuation=first.continuation))
    assert calls==['https://source.example/used/tata-altroz/','https://source.example/used/tata-altroz/page-2']
    assert second.continuation is None
