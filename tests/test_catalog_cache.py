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


def test_observed_models_return_before_slow_live_refresh_and_survive_failure(monkeypatch):
    catalog._model_cache.clear()
    catalog._model_pending.clear()
    monkeypatch.setattr(catalog,'observed_models',lambda brand:[{'name':'F-Pace','catalog_verified':'observed_inventory'}])
    tasks=[]
    monkeypatch.setattr(catalog._model_refresh,'submit',lambda fn,*args:tasks.append((fn,args)))
    def unavailable(brand):raise RuntimeError('upstream unavailable')
    monkeypatch.setattr(catalog,'live_models',unavailable)
    assert catalog.catalog_models('Jaguar')[0]['name']=='F-Pace'
    assert len(tasks)==1
    tasks[0][0](*tasks[0][1])
    assert catalog.catalog_models('Jaguar')[0]['catalog_verified']=='observed_inventory'
    assert not catalog._model_pending
    catalog._model_cache.clear()


def test_observed_variant_names_also_expose_existing_base_family_normalization():
    rows=catalog._observed_model_names('Mercedes-Benz',[
        {'name':'E Class E 220d'},{'name':'E-Class E 200 Exclusive'}])
    assert 'E-Class' in [row['name'] for row in rows]
    assert catalog._observed_model_names('Volvo',[{'name':'XC60 B5 Ultimate'}])[0]['name']=='XC60'
    names=[r['name'] for r in catalog._observed_model_names('BMW',[
        {'name':'3-Series 320d'},{'name':'3 Series Gran Limousine'},{'name':'6-Series GT 630d'}])]
    assert '3 Series' in names and '6 Series' in names and 'Series' not in names
