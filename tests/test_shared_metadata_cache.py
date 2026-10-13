import json
import os
import subprocess
import sys
import time
from uuid import uuid4

import pytest
from src import shared_metadata_cache as cache
from src import source_intelligence as registry
from src.search_timing import timed_request, measure_call, server_timing


def test_shared_hit_does_not_renew_l1_freshness_or_leak_mutation(monkeypatch):
    clock = [100]
    calls = []
    monkeypatch.setenv('CARSCANNER_REDIS_URL', 'redis://localhost:6379')
    monkeypatch.setattr(registry, '_metadata_cache', None)
    monkeypatch.setattr(registry.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(cache, 'get', lambda _: calls.append(1) or ([{'name': 'Shared'}], 2))
    monkeypatch.setattr(registry, 'load_source_registry', lambda: pytest.fail('shared hit should avoid DB'))
    rows = registry._search_registry(15)
    rows[0]['name'] = 'private mutation'
    clock[0] = 101
    assert registry._search_registry(15)[0]['name'] == 'Shared'
    clock[0] = 103
    assert registry._search_registry(15)[0]['name'] == 'Shared' and len(calls) == 2


def test_shared_failure_falls_back_and_circuit_stops_repeated_calls(monkeypatch):
    calls = []
    monkeypatch.setenv('CARSCANNER_REDIS_URL', 'redis://localhost:6379')
    monkeypatch.setattr(cache, '_retry_after', 0)
    monkeypatch.setattr(cache, '_url', 'redis://localhost:6379')
    class Broken:
        def pipeline(self, **kwargs):
            calls.append(1)
            raise RuntimeError('private-password-never-log')
    monkeypatch.setattr(cache, '_client', Broken())
    assert cache.get('test') is None and cache.get('test') is None
    assert len(calls) == 1
    monkeypatch.setattr(registry, '_metadata_cache', None)
    monkeypatch.setattr(registry, 'load_source_registry', lambda: [{'name': 'Database'}])
    assert registry._search_registry(15)[0]['name'] == 'Database'


def test_cache_key_hides_credentials_and_separates_database_identity():
    one = cache.cache_key(('postgres://user:secret@host/db', 1))
    two = cache.cache_key(('postgres://user:secret@host/other', 1))
    assert one != two and 'secret' not in one and 'user' not in one


def test_timing_context_resets_after_exception_and_is_thread_isolated():
    from concurrent.futures import ThreadPoolExecutor
    @timed_request
    def run(stage):
        measure_call(stage, lambda: None)
        return server_timing()
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(run, ['first', 'second']))
    assert 'second' not in values[0] and 'first' not in values[1]
    assert all('total;dur=' in value for value in values)
    @timed_request
    def fail():
        raise ValueError('test')
    with pytest.raises(ValueError): fail()
    assert server_timing() is None


@pytest.mark.integration
def test_real_redis_cross_process_hit_expiry_and_corrupt_data(monkeypatch):
    redis = pytest.importorskip('redis')
    url = os.getenv('CARSCANNER_TEST_REDIS_URL')
    if not url: pytest.skip('Set CARSCANNER_TEST_REDIS_URL for disposable Redis')
    from urllib.parse import urlsplit
    assert urlsplit(url).hostname in {'127.0.0.1', 'localhost', '::1'}
    monkeypatch.setenv('CARSCANNER_REDIS_URL', url)
    monkeypatch.setattr(cache, '_retry_after', 0)
    identity = 'integration-' + uuid4().hex
    client = redis.Redis.from_url(url, decode_responses=True)
    key = cache.cache_key(identity)
    try:
        cache.put(identity, [{'name': 'Shared process'}], 5)
        program = 'import json; from src.shared_metadata_cache import get; print(json.dumps(get(' + repr(identity) + ')))'
        result = subprocess.run([sys.executable, '-c', program], env=os.environ.copy(),
                                check=True, capture_output=True, text=True, timeout=10)
        rows, remaining = json.loads(result.stdout)
        assert rows == [{'name': 'Shared process'}] and 0 < remaining <= 5
        client.set(key, '{invalid', px=1000)
        assert cache.get(identity) is None
        cache.put(identity, [{'name': 'Expires'}], 0.1)
        time.sleep(0.15)
        assert cache.get(identity) is None
        cache.put(identity, [{'name': 'Bounded'}], 999)
        assert 0 < client.pttl(key) <= 15000
    finally:
        client.delete(key)
        client.close()
