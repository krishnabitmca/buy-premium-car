from contextlib import contextmanager
from src import inventory_coverage as coverage
from src import live_marketplaces as lm


def test_coverage_audits_both_conditions_and_never_equates_empty_with_no_market(monkeypatch):
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,*args): pass
        def fetchall(self): return [
            {'brand':'tata','source':'A','status':'failed'},
            {'brand':'tata','source':'A','status':'completed'}]
    class Connection(Cursor):
        def cursor(self): return Cursor()
    monkeypatch.setattr(coverage,'require_database',lambda:None)
    monkeypatch.setattr(coverage,'_connect',Connection)
    monkeypatch.setattr(coverage,'baseline_brand_demands',lambda:[{'brand':'Tata'},{'brand':'Citroen'}])
    requests=[]
    def search(**kwargs):
        requests.append(kwargs)
        n=2 if kwargs['query']=='Tata' and kwargs['condition']=='used' else 0
        return [],[],n,{'sources':['A'] if n else [],'cities':['Delhi','Chennai'] if n else []}
    monkeypatch.setattr(coverage,'search_inventory',search)
    report=coverage.coverage_report()
    assert len(requests)==4 and all(r['require_persistence'] for r in requests)
    assert not report['complete_market_coverage'] and report['scope']=='india'
    tata=report['brands'][0]
    assert tata['conditions']['used']['indexed_results']==2
    assert tata['conditions']['demo']['status']=='coverage_gap'
    assert tata['scans']==[{'brand':'tata','source':'A','status':'failed'}]
    assert report['brands'][1]['conditions']['used']['status']=='coverage_gap'


def test_accented_make_identity_and_configured_marketplace_slugs(monkeypatch):
    monkeypatch.setattr(lm,'_known_brand_names',lambda:['Citroen','Maruti Suzuki','MG'])
    assert lm._infer_brand_model('Citroën C3',None,None)==('Citroen','C3')
    assert lm._identity_matches_query({'brand':'Citroën','model':'C3'},'Citroen')
    assert lm._query_parts('Citroën C3')==('Citroen','C3')
    assert lm._slug('Citroën')=='citroen'
    source={'name':'A','adapter_status':'live','brands':['all'],
        'brand_query_url_template':'https://example.invalid/used-{brand_slug}',
        'metadata':{'brand_slug_overrides':{'MG Motor':'mg','Maruti Suzuki':'maruti'}}}
    assert lm._targeted_source_urls('MG',registry=[source])['A'].endswith('used-mg')
    assert lm._targeted_source_urls('Maruti Suzuki',registry=[source])['A'].endswith('used-maruti')


def test_next_page_aria_label_is_followed_without_rel_next():
    assert lm._next_page_url('<a aria-label="Next page" href="?page=2">More</a>',
        'https://example.invalid/cars')=='https://example.invalid/cars?page=2'
