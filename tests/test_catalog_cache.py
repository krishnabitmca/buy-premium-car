from concurrent.futures import ThreadPoolExecutor
from api import catalog


def test_catalog_single_fetch_under_concurrency_expiry_and_mutation_isolation(monkeypatch):
    catalog._model_cache.clear()
    clock=[1]
    monkeypatch.setattr(catalog.time,'monotonic',lambda:clock[0])
    calls=[]
    monkeypatch.setattr(catalog,'live_models',lambda brand:calls.append(brand) or [{'name':'X5','url':'https://catalog.example/x5'}])
    with ThreadPoolExecutor(max_workers=4) as executor:
        results=list(executor.map(catalog.catalog_models,['BMW']*4))
    assert calls==['BMW']
    results[0][0]['name']='changed'
    assert catalog.catalog_models('BMW')[0]['name']=='X5'
    clock[0]=902
    catalog.catalog_models('BMW')
    assert calls==['BMW','BMW']
    catalog._model_cache.clear()


def test_empty_model_fetch_is_retried_and_cache_is_bounded(monkeypatch):
    catalog._model_cache.clear()
    calls=[]
    def load(brand):
        calls.append(brand)
        return [] if len(calls)==1 else [{'name':'City'}]
    monkeypatch.setattr(catalog,'live_models',load)
    assert catalog.catalog_models('Honda')==[]
    assert catalog.catalog_models('Honda')==[{'name':'City','slug':'city'}]
    for n in range(70): catalog.catalog_models(str(n))
    assert len(catalog._model_cache)==64
    catalog._model_cache.clear()
