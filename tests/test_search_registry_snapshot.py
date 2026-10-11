from concurrent.futures import ThreadPoolExecutor

from src import source_intelligence as registry


def test_search_metadata_cache_is_bounded_isolated_and_not_mutable(monkeypatch):
    clock=[0]
    database=['one']
    reads=[]
    monkeypatch.setattr(registry,'_metadata_cache',None)
    monkeypatch.setattr(registry.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr('src.source_registry_db.database_url',lambda:database[0])
    monkeypatch.setattr('src.source_registry_db.enabled',lambda:True)
    def load():
        reads.append(1)
        return [{'name':str(len(reads))}]
    monkeypatch.setattr('src.source_registry_db.load_registry',load)
    @registry.with_source_registry(metadata_ttl=15)
    def request():
        rows=registry.load_source_registry()
        name=rows[0]['name']
        rows[0]['name']='changed only in this request'
        return name
    assert request()=='1' and request()=='1'
    clock[0]=16
    assert request()=='2'
    database[0]='two'
    assert request()=='3'


def test_request_reads_once_and_next_request_sees_registry_changes(monkeypatch):
    reads=[]
    def load():
        reads.append(1)
        return [{'name':str(len(reads))}]
    monkeypatch.setattr('src.source_registry_db.enabled',lambda:True)
    monkeypatch.setattr('src.source_registry_db.load_registry',load)
    @registry.with_source_registry
    def request():
        return [registry.load_source_registry()[0]['name'] for _ in range(50)]
    assert request()==['1']*50
    assert request()==['2']*50
    assert len(reads)==2 and registry._request_registry.get() is None


def test_request_registry_is_thread_isolated_and_resets_on_error(monkeypatch):
    import threading
    barrier=threading.Barrier(2)
    monkeypatch.setattr('src.source_registry_db.enabled',lambda:True)
    monkeypatch.setattr('src.source_registry_db.load_registry',lambda:[{'name':threading.current_thread().name}])
    @registry.with_source_registry
    def request(fail=False):
        barrier.wait(timeout=3)
        name=registry.load_source_registry()[0]['name']
        if fail:
            raise ValueError(name)
        return name
    def run(fail):
        try:
            return request(fail)
        except ValueError as exc:
            return str(exc)
        finally:
            assert registry._request_registry.get() is None
    with ThreadPoolExecutor(max_workers=2) as executor:
        names=list(executor.map(run,[False,True]))
    assert len(set(names))==2
