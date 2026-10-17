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
