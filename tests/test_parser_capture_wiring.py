"""Capture is an explicit diagnostic on existing background acquisition only."""
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from tests.test_verify_scan_ledger import operator
from src.source_adapters import AdapterRequest, AdapterResult, BuiltinMarketplaceAdapter
from src import live_marketplaces as lm

HTML = Path('tests/fixtures/reviewed_fusion.html').read_text(encoding='utf-8')
BASE = 'https://fusioncars.in/collections/'


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setattr(lm, '_known_brand_names', lambda: ['Mercedes-Benz'])
    monkeypatch.setattr('src.source_adapters.adapter_execution_allowed', lambda *_: True)
    monkeypatch.setattr('src.source_adapters.record_adapter_execution', lambda *a, **k: None)
    fetch = Mock(return_value=HTML)
    monkeypatch.setattr('src.source_adapters.fetch_text', fetch)
    source = dict(name='Fusion Cars', source_id=uuid4(), url=BASE, parser_strategy='fusion_cards')
    return BuiltinMarketplaceAdapter(source), fetch


@pytest.mark.parametrize('enabled,background,buffer_present', [
    ('true', False, True), ('false', True, True), ('true', True, False),
])
def test_environment_or_api_request_alone_never_captures(adapter, monkeypatch,
                                                         enabled, background, buffer_present):
    instance, fetch = adapter
    monkeypatch.setenv('CARSCANNER_PARSER_CAPTURE_ENABLED', enabled)
    buffer = Mock()
    result = instance.fetch(AdapterRequest(continuation={} if background else None),
                            _capture=buffer if buffer_present else None)
    assert result.status == 'live' and result.listings
    buffer.capture.assert_not_called()
    assert fetch.call_count == 1


def test_background_capture_reuses_response_and_real_scan_generation(adapter, monkeypatch):
    instance, fetch = adapter
    monkeypatch.setenv('CARSCANNER_PARSER_CAPTURE_ENABLED', 'true')
    buffer = Mock()
    result = instance.fetch(AdapterRequest(continuation={}), _capture=buffer)
    assert result.status == 'live' and result.listings
    assert fetch.call_count == 1
    buffer.capture.assert_called_once_with(HTML, source_url=BASE,
        scan_generation=result.scan_evidence['generation_id'])
    buffer.export.assert_not_called()


def test_capture_hook_is_not_used_for_other_parser_strategy(adapter, monkeypatch):
    instance, fetch = adapter
    instance.source['parser_strategy'] = 'embedded_json'
    monkeypatch.setenv('CARSCANNER_PARSER_CAPTURE_ENABLED', 'true')
    monkeypatch.setattr(lm, 'parse_embedded_marketplace_listings', lambda *a: [])
    monkeypatch.setattr('src.source_adapters.parse_live_listings', lambda *a: [])
    monkeypatch.setattr('src.source_adapters.parse_visible_listing_links', lambda *a: [])
    buffer = Mock()
    instance.fetch(AdapterRequest(continuation={}), _capture=buffer)
    buffer.capture.assert_not_called()
    assert fetch.call_count == 1


def test_worker_forwards_private_buffer_but_never_exports_before_claim_fence(monkeypatch):
    from src import inventory_refresh_worker as worker, crawl_leases
    source_id = uuid4()
    source = dict(source_id=source_id, name='Fusion Cars', url=BASE, adapter_status='live')
    monkeypatch.setattr(worker, 'load_registry', lambda: [source])
    monkeypatch.setattr(lm, '_known_brand_names', lambda: ['Mercedes-Benz'])
    monkeypatch.setattr(crawl_leases, 'acquire', lambda _: 'lease')
    monkeypatch.setattr(crawl_leases, 'release', lambda *_: None)
    cursor = Mock()
    cursor.fetchone.return_value = None  # The old claim has been superseded.
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    connection.cursor.return_value = cursor
    monkeypatch.setattr(worker, '_connect', lambda: connection)
    fetch = Mock(return_value=AdapterResult('Fusion Cars', status='live'))
    monkeypatch.setattr(BuiltinMarketplaceAdapter, 'fetch', fetch)
    buffer = Mock()
    job = dict(source_id=source_id, source_name='Fusion Cars', refresh_id=1,
               attempt_count=2, started_at='2026-10-20T00:00:00+00:00', metadata={})
    assert worker.process_job(job, _capture=buffer) == {'superseded': 1}
    assert fetch.call_args.kwargs['_capture'] is buffer
    buffer.export.assert_not_called()


@pytest.mark.parametrize('export_status', ['exported', 'export_failed', 'missing'])
def test_export_runs_after_exact_claim_commit_and_never_retries_worker(operator, monkeypatch,
                                                                       tmp_path, export_status):
    from scripts import verify_scan_ledger as verifier
    from src import source_registry_db
    monkeypatch.setenv('CARSCANNER_PARSER_CAPTURE_ENABLED', 'true')
    source_id = operator['job']['source_id']
    generation_id = uuid4()
    operator['batch'].update(generation_id=generation_id, source_id=source_id,
                            completed_at=operator['job']['started_at'] + timedelta(seconds=1))
    monkeypatch.setattr(source_registry_db, 'load_registry', lambda: [dict(
        source_id=source_id, name='Fusion Cars', url=BASE, parser_strategy='fusion_cards')])
    target = tmp_path / 'new-capture'
    if export_status == 'export_failed':
        target.mkdir()  # Never overwrite an existing diagnostic directory.
    def committed(job, *, _capture):
        assert job == operator['job']
        if export_status != 'missing':
            _capture.capture(HTML, source_url=BASE, scan_generation=str(generation_id))
        return {'observations': 2}
    operator['process'].side_effect = committed
    result = verifier.verify('Fusion Cars', capture_directory=target)
    operator['claim'].assert_called_once()
    operator['process'].assert_called_once()
    assert result['capture']['status'] == export_status
    assert result['capture']['inventory_commit'] == 'verified'
    assert result['ok'] == (export_status == 'exported')
    if export_status != 'export_failed':
        receipt = json.loads((target / 'receipt.json').read_text(encoding='utf-8'))
        assert receipt['generation_id'] == str(generation_id)
        assert receipt['batch_id'] == str(operator['batch']['batch_id'])
        assert receipt['refresh_id'] == operator['job']['refresh_id']
        assert receipt['attempt_count'] == operator['job']['attempt_count']
        assert receipt['claim_started_at'] == operator['job']['started_at'].isoformat()
        assert receipt['inventory_commit'] == 'verified'


def test_capture_directory_cannot_enable_unreviewed_source_before_claim(operator, monkeypatch, tmp_path):
    from scripts import verify_scan_ledger as verifier
    from src import source_registry_db
    monkeypatch.setenv('CARSCANNER_PARSER_CAPTURE_ENABLED', 'true')
    monkeypatch.setattr(source_registry_db, 'load_registry', lambda: [dict(
        source_id=operator['job']['source_id'], name='Fixture Dealer', url='https://example.invalid/',
        parser_strategy='embedded_json')])
    with pytest.raises(ValueError, match='reviewed Fusion adapter'):
        verifier.verify('Fixture Dealer', capture_directory=tmp_path/'new-capture')
    operator['claim'].assert_not_called()
    operator['process'].assert_not_called()
