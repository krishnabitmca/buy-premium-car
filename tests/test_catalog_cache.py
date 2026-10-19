from concurrent.futures import ThreadPoolExecutor
import pytest
from api import catalog


@pytest.fixture(autouse=True)
def isolate_model_metadata(monkeypatch):
    catalog._model_cache.clear();catalog._model_pending.clear();catalog._enrichment_pending.clear()
    monkeypatch.setattr(catalog,'observed_models',lambda brand:[])
    monkeypatch.setattr(catalog,'_observed_refresh',ImmediateExecutor())
    monkeypatch.setattr(catalog,'_model_refresh',ImmediateExecutor())
    yield
    catalog._model_cache.clear();catalog._model_pending.clear();catalog._enrichment_pending.clear()


class ImmediateExecutor:
    def submit(self,fn,*args):fn(*args)


def test_catalog_single_fetch_under_concurrency_expiry_and_mutation_isolation(monkeypatch):
    catalog._model_cache.clear()
    clock=[1]
    monkeypatch.setattr(catalog.time,'monotonic',lambda:clock[0])
    calls=[]
    monkeypatch.setattr(catalog,'_model_refresh',ImmediateExecutor())
    monkeypatch.setattr(catalog,'live_models',lambda brand:calls.append(brand) or [{'name':'X5','url':'https://catalog.example/x5'}])
    with ThreadPoolExecutor(max_workers=4) as executor:
        def request(brand):
            try:return catalog.catalog_models(brand)
            except catalog.CatalogPending:return None
        results=list(executor.map(request,['BMW']*4))
    assert calls==['BMW']
    next(row for row in results if row)[0]['name']='changed'
    assert catalog.catalog_models('BMW')[0]['name']=='X5'
    clock[0]=902
    catalog.catalog_models('BMW')
    assert calls==['BMW','BMW']
    catalog._model_cache.clear()


def test_empty_model_fetch_is_retried_and_cache_is_bounded(monkeypatch):
    catalog._model_cache.clear()
    calls=[]
    clock=[1]
    monkeypatch.setattr(catalog.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(catalog,'_model_refresh',ImmediateExecutor())
    def load(brand):
        calls.append(brand)
        return [] if len(calls)==1 else [{'name':'City'}]
    monkeypatch.setattr(catalog,'live_models',load)
    with pytest.raises(catalog.CatalogPending):catalog.catalog_models('Honda')
    with pytest.raises(catalog.CatalogPending):catalog.catalog_models('Honda')
    assert calls==['Honda']
    clock[0]=32
    assert catalog.catalog_models('Honda')==[{'name':'City','slug':'city'}]
    for n in range(70): catalog.catalog_models(str(n))
    assert len(catalog._model_cache)==64
    catalog._model_cache.clear()


def test_observed_models_return_before_slow_live_refresh_and_survive_failure(monkeypatch):
    catalog._model_cache.clear()
    catalog._model_pending.clear()
    monkeypatch.setattr(catalog,'observed_models',lambda brand:[{'name':'F-Pace','catalog_verified':'observed_inventory'}])
    tasks=[]
    monkeypatch.setattr(catalog._observed_refresh,'submit',lambda fn,*args:tasks.append((fn,args)))
    def unavailable(brand):
        # Observed names are published before the background external request.
        assert catalog.catalog_models(brand)[0]['name']=='F-Pace'
        raise RuntimeError('upstream unavailable')
    monkeypatch.setattr(catalog,'live_models',unavailable)
    with pytest.raises(catalog.CatalogPending):catalog.catalog_models('Jaguar')
    assert len(tasks)==1
    tasks[0][0](*tasks[0][1])
    assert catalog.catalog_models('Jaguar')[0]['catalog_verified']=='observed_inventory'
    assert not catalog._model_pending
    catalog._model_cache.clear()


def test_cold_model_requests_never_call_database_or_live_provider_on_http_thread(monkeypatch):
    tasks=[]
    monkeypatch.setattr(catalog._observed_refresh,'submit',lambda fn,*args:tasks.append((fn,args)))
    def forbidden(_):raise AssertionError('HTTP thread must not fetch metadata')
    monkeypatch.setattr(catalog,'observed_models',forbidden)
    monkeypatch.setattr(catalog,'live_models',forbidden)
    for _ in range(4):
        with pytest.raises(catalog.CatalogPending):catalog.catalog_models('BMW')
    assert len(tasks)==1


def test_observed_metadata_is_not_starved_by_queued_external_enrichment(monkeypatch):
    external=[]
    monkeypatch.setattr(catalog._model_refresh,'submit',lambda fn,*args:external.append((fn,args)))
    monkeypatch.setattr(catalog,'observed_models',lambda brand:[{'name':'City' if brand=='Honda' else 'X5'}])
    assert catalog.catalog_models('BMW')[0]['name']=='X5'
    assert catalog.catalog_models('Honda')[0]['name']=='City'
    assert len(external)==2  # Neither external request has run.


def test_full_external_backlog_does_not_block_observed_model_metadata(monkeypatch):
    catalog._enrichment_pending.update(str(n) for n in range(16))
    monkeypatch.setattr(catalog,'observed_models',lambda brand:[{'name':'City'}])
    def forbidden(*_args):raise AssertionError('External backlog must stay bounded')
    monkeypatch.setattr(catalog._model_refresh,'submit',forbidden)
    assert catalog.catalog_models('Honda')[0]['name']=='City'
    assert not catalog._model_pending
    assert len(catalog._enrichment_pending)==16


@pytest.mark.parametrize('external_failure',[False,True])
def test_transient_observed_lookup_retries_without_thirty_second_empty_cache(monkeypatch,external_failure):
    clock=[100];calls=[]
    monkeypatch.setattr(catalog.time,'monotonic',lambda:clock[0])
    def observed(_):
        calls.append(1)
        if len(calls)==1:raise catalog.ObservedCatalogUnavailable()
        return [{'name':'Q5','catalog_verified':'observed_inventory'}]
    def external(_):
        if external_failure:raise RuntimeError('External outage must not extend fast retry')
        return []
    monkeypatch.setattr(catalog,'observed_models',observed)
    monkeypatch.setattr(catalog,'live_models',external)
    with pytest.raises(catalog.CatalogPending):catalog.catalog_models('Audi')
    clock[0]=100.5
    with pytest.raises(catalog.CatalogPending):catalog.catalog_models('Audi')
    assert len(calls)==1
    clock[0]=101.1
    assert catalog.catalog_models('Audi')[0]['name']=='Q5'
    assert len(calls)==2 and not catalog._model_pending


def test_observed_variant_names_also_expose_existing_base_family_normalization():
    rows=catalog._observed_model_names('Mercedes-Benz',[
        {'name':'E Class E 220d'},{'name':'E-Class E 200 Exclusive'}])
    assert 'E-Class' in [row['name'] for row in rows]
    assert catalog._observed_model_names('Volvo',[{'name':'XC60 B5 Ultimate'}])[0]['name']=='XC60'
    names=[r['name'] for r in catalog._observed_model_names('BMW',[
        {'name':'3-Series 320d'},{'name':'3 Series Gran Limousine'},{'name':'6-Series GT 630d'}])]
    assert '3 Series' in names and '6 Series' in names and 'Series' not in names
def test_brand_taxonomy_returns_before_single_background_discovery(monkeypatch):
    from api import catalog
    from src.car_catalog import CAR_MAKES
    tasks=[]
    class Executor:
        def submit(self, fn):tasks.append(fn)
    monkeypatch.setattr(catalog,'_brand_cache',[])
    monkeypatch.setattr(catalog,'_brand_next_refresh',0)
    monkeypatch.setattr(catalog,'_brand_refresh_pending',False)
    monkeypatch.setattr(catalog,'_model_refresh',Executor())
    monkeypatch.setattr(catalog,'live_brands',lambda:[{'name':'Discovered Example','catalog_verified':'discovered'}])
    for _ in range(4):
        rows=catalog.catalog_brands()
        assert {row['name'] for row in rows}==set(CAR_MAKES)
        assert all(row['inventory_coverage']=='unverified' for row in rows)
    assert len(tasks)==1
    tasks.pop()()
    assert any(row['name']=='Discovered Example' for row in catalog.catalog_brands())
    assert not tasks


def test_brand_discovery_failure_retains_metadata_and_backs_off(monkeypatch):
    from api import catalog
    import time
    monkeypatch.setattr(catalog,'_brand_cache',[{'name':'Observed Example'}])
    monkeypatch.setattr(catalog,'_brand_next_refresh',0)
    monkeypatch.setattr(catalog,'_brand_refresh_pending',True)
    def fail():raise RuntimeError('unavailable')
    monkeypatch.setattr(catalog,'live_brands',fail)
    catalog._refresh_brands()
    assert catalog._brand_cache==[{'name':'Observed Example'}]
    assert not catalog._brand_refresh_pending
    assert catalog._brand_next_refresh>time.monotonic()

