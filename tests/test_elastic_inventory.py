from datetime import datetime, timedelta, timezone
import json

from src import elastic_inventory as elastic


def manifest():
    now = datetime.now(timezone.utc)
    return dict(schema=1, year=now.year, generation='test', revision=1,
                expire_minutes=10080, valid_until=(now + timedelta(hours=1)).isoformat())


def test_offer_budget_is_nested_and_model_is_complete_tokens():
    body = elastic.search_body(manifest(), query='BMW X5', condition='used',
                               budget_min=35, budget_max=40, limit=50, offset=50)
    serialized = json.dumps(body)
    assert 'offers.price' in serialized
    nested = body['query']['bool']['filter'][-1]['nested']
    assert nested['path'] == 'offers'
    assert nested['query']['bool']['filter'][0]['range']['offers.price'] == {'gte': 35, 'lte': 40}
    assert {'wildcard': {'identity': '* x5 *'}} in body['query']['bool']['filter']
    assert body['from'] == 50 and body['track_total_hits'] is True
    assert 'destination' not in serialized


def test_expired_manifest_and_provider_outage_fall_back(monkeypatch):
    monkeypatch.setenv('CARSCANNER_SEARCH_ENGINE', 'elasticsearch')
    monkeypatch.setattr(elastic.inventory_db, 'enabled', lambda: True)
    expected = (['canonical'], [], 1)
    monkeypatch.setattr(elastic.inventory_db, 'search_inventory', lambda **kw: expected)
    stale = manifest()
    stale['valid_until'] = '2020-01-01T00:00:00+00:00'
    monkeypatch.setattr(elastic, '_retry_after', 0)
    monkeypatch.setattr(elastic, 'request', lambda *a, **k: {'_source': stale})
    assert elastic.search_inventory(return_count=True) == expected
    assert elastic.backend() == 'postgresql'
    monkeypatch.setattr(elastic, '_retry_after', 0)
    def fail(*a, **k):
        raise elastic.IndexUnavailable('expired trial')
    monkeypatch.setattr(elastic, 'request', fail)
    assert elastic.search_inventory(return_count=True) == expected


def test_request_requires_https_and_a_server_credential(monkeypatch):
    monkeypatch.setenv('CARSCANNER_ELASTICSEARCH_URL', 'http://example.invalid')
    monkeypatch.setenv('CARSCANNER_ELASTICSEARCH_API_KEY', 'never-log-this')
    import pytest
    with pytest.raises(elastic.IndexUnavailable, match='configuration unavailable'):
        elastic.request('GET', '/_doc/manifest')


def test_new_index_strict_mapping_accepts_every_published_manifest_field(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    monkeypatch.setattr(elastic,'require_database',lambda:None)
    monkeypatch.setattr(elastic,'_connect',lambda:nullcontext(SimpleNamespace(execute=lambda *args:[])))
    monkeypatch.setattr(elastic,'revision',lambda conn:7)
    monkeypatch.setattr(elastic.inventory_db,'search_inventory',lambda **kwargs:([],[]))
    mapping={};published=[]
    def fake_request(method,path,body=None,**kwargs):
        if path=='/_mapping':raise elastic.IndexUnavailable('Elasticsearch index missing')
        if method=='PUT' and path=='':mapping.update(body['mappings'])
        if method=='PUT' and path.startswith('/_doc/manifest'):
            assert mapping['dynamic']=='strict'
            assert set(body)<=set(mapping['properties'])
            assert body['used_expire_minutes']==2880 and body['demo_expire_minutes']==1440
            published.append(body)
        return {}
    monkeypatch.setattr(elastic,'request',fake_request)
    result=elastic.rebuild()
    assert result['ok'] and result['count']==0 and len(published)==1
