"""Safe, deterministic Elasticsearch indexer failure diagnostics."""
import logging
from urllib.error import HTTPError, URLError

import pytest

from src import elastic_inventory as elastic


def configure(monkeypatch):
    monkeypatch.setenv('CARSCANNER_ELASTICSEARCH_URL', 'https://elastic.example.invalid')
    monkeypatch.setenv('CARSCANNER_ELASTICSEARCH_INDEXER_API_KEY', 'PRIVATE-API-KEY')
    monkeypatch.setenv('CARSCANNER_ELASTICSEARCH_API_KEY', 'PRIVATE-SEARCH-KEY')


@pytest.mark.parametrize('method,path,stage', [
    ('GET', '/_mapping', 'mapping_lookup'),
    ('PUT', '', 'mapping_create'),
    ('POST', '/_bulk?refresh=wait_for', 'bulk_upload'),
    ('PUT', '/_doc/manifest?refresh=wait_for', 'manifest_publish'),
    ('POST', '/_delete_by_query?conflicts=proceed', 'generation_cleanup'),
])
def test_indexer_http_failure_reports_only_fixed_stage_and_status(monkeypatch, caplog, method, path, stage):
    configure(monkeypatch)

    def fail(_request, timeout):
        raise HTTPError('https://elastic.example.invalid/PRIVATE-URL', 429,
                        'PRIVATE-VENDOR-DETAILS', {}, None)

    monkeypatch.setattr(elastic, 'urlopen', fail)
    with caplog.at_level(logging.WARNING, logger=elastic.__name__):
        with pytest.raises(elastic.IndexUnavailable, match='request failed'):
            elastic.request(method, path, {} if method != 'GET' else None, indexer=True)
    assert f'stage={stage}' in caplog.text
    assert 'category=http' in caplog.text
    assert 'status=429' in caplog.text
    for secret in ('PRIVATE-URL', 'PRIVATE-VENDOR-DETAILS', 'PRIVATE-API-KEY'):
        assert secret not in caplog.text


def test_indexer_network_error_has_no_vendor_detail(monkeypatch, caplog):
    configure(monkeypatch)

    def fail(_request, timeout):
        raise URLError('PRIVATE-HOST-DETAILS')

    monkeypatch.setattr(elastic, 'urlopen', fail)
    with caplog.at_level(logging.WARNING, logger=elastic.__name__):
        with pytest.raises(elastic.IndexUnavailable):
            elastic.request('POST', '/_bulk?refresh=wait_for', '{}\\n', indexer=True, ndjson=True)
    assert 'stage=bulk_upload category=network status=unknown' in caplog.text
    assert 'PRIVATE-HOST-DETAILS' not in caplog.text


def test_search_request_does_not_emit_indexer_failure_log(monkeypatch, caplog):
    configure(monkeypatch)

    def fail(_request, timeout):
        raise HTTPError('https://elastic.example.invalid/PRIVATE-URL', 503,
                        'PRIVATE-ERROR', {}, None)

    monkeypatch.setattr(elastic, 'urlopen', fail)
    with caplog.at_level(logging.WARNING, logger=elastic.__name__):
        with pytest.raises(elastic.IndexUnavailable):
            elastic.request('GET', '/_doc/manifest')
    assert 'elastic_indexer_request_failed' not in caplog.text


def test_cli_reason_is_allowlisted_and_never_echoes_exception_text():
    assert elastic.rebuild_failure_reason(elastic.IndexUnavailable(
        'Snapshot expired before publication')) == 'snapshot_expired'
    assert elastic.rebuild_failure_reason(elastic.IndexUnavailable(
        'PRIVATE-SECRET-TOKEN')) == 'index_unavailable'
    assert elastic.rebuild_failure_reason(ValueError('PRIVATE-SECRET-TOKEN')) == 'unexpected'


@pytest.mark.parametrize('status,expected', [
    (404, 'Elasticsearch index missing'),
    (401, 'Elasticsearch request failed'),
    (403, 'Elasticsearch request failed'),
    (429, 'Elasticsearch request failed'),
    (503, 'Elasticsearch request failed'),
])
def test_mapping_lookup_only_treats_404_as_missing(monkeypatch, caplog, status, expected):
    configure(monkeypatch)

    def fail(_request, timeout):
        raise HTTPError('https://elastic.example.invalid/PRIVATE-URL', status,
                        'PRIVATE-ERROR', {}, None)

    monkeypatch.setattr(elastic, 'urlopen', fail)
    with caplog.at_level(logging.WARNING, logger=elastic.__name__):
        with pytest.raises(elastic.IndexUnavailable, match=expected):
            elastic.request('GET', '/_mapping', indexer=True)
    assert f'stage=mapping_lookup category=http status={status}' in caplog.text
    assert 'PRIVATE-URL' not in caplog.text
    assert 'PRIVATE-ERROR' not in caplog.text


def test_rebuild_does_not_create_mapping_after_transient_lookup_failure(monkeypatch):
    monkeypatch.setattr(elastic, 'require_database', lambda: None)
    calls = []

    def fake_request(method, path, body=None, *, indexer=False):
        calls.append((method, path))
        raise elastic.IndexUnavailable('Elasticsearch request failed')

    monkeypatch.setattr(elastic, 'request', fake_request)
    with pytest.raises(elastic.IndexUnavailable, match='request failed'):
        elastic.rebuild()
    assert calls == [('GET', '/_mapping')]


def test_rebuild_creates_mapping_only_after_explicit_missing_index(monkeypatch):
    monkeypatch.setattr(elastic, 'require_database', lambda: None)
    calls = []

    def fake_request(method, path, body=None, *, indexer=False):
        calls.append((method, path))
        if method == 'GET':
            raise elastic.IndexMissing('Elasticsearch index missing')
        return {}

    class StopBeforeSnapshot(Exception):
        pass

    def stop_before_snapshot():
        raise StopBeforeSnapshot()

    monkeypatch.setattr(elastic, 'request', fake_request)
    monkeypatch.setattr(elastic, '_connect', stop_before_snapshot)
    with pytest.raises(StopBeforeSnapshot):
        elastic.rebuild()
    assert calls == [('GET', '/_mapping'), ('PUT', '')]


def test_rebuild_rejects_spoofed_missing_index_message(monkeypatch):
    """An ordinary failure with matching text must never authorize index creation."""
    monkeypatch.setattr(elastic, 'require_database', lambda: None)
    calls = []

    def fake_request(method, path, body=None, *, indexer=False):
        calls.append((method, path))
        raise elastic.IndexUnavailable('Elasticsearch index missing')

    monkeypatch.setattr(elastic, 'request', fake_request)
    with pytest.raises(elastic.IndexUnavailable, match='index missing'):
        elastic.rebuild()
    assert calls == [('GET', '/_mapping')]
