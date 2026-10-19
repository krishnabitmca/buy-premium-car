import pytest
from src.scan_contract import generation, outcome, scan_scope
from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter


def test_generations_are_scoped_and_never_authorize_absence():
    request = AdapterRequest(query="Honda City", continuation={})
    source = {"name": "Fixture", "parser_strategy": "fixture"}
    _, fingerprint = scan_scope(source, request, ["https://fixture.invalid/"])
    first = generation({}, fingerprint)
    assert generation({"scan_generation": first}, fingerprint) == first
    assert generation({}, fingerprint)["generation_id"] != first["generation_id"]
    for pending in (True, False):
        evidence = outcome(first, pending=pending, background=True)
        assert not evidence["completeness_verified"]
        assert not evidence["absence_reconciliation_permitted"]
    _, changed = scan_scope({**source, "parser_version": "v2"}, request, ["https://fixture.invalid/"])
    assert changed != fingerprint
    assert generation({"scan_generation": first}, changed)["generation_id"] != first["generation_id"]


@pytest.mark.parametrize('top_level', [None, ''])
def test_metadata_parser_fallback_changes_fingerprint(top_level):
    source = {'name': 'Fixture', 'parser_strategy': top_level,
              'metadata': {'parser_strategy': 'first'}}
    request = AdapterRequest(continuation={})
    _, first = scan_scope(source, request, ['https://fixture.invalid/'])
    _, second = scan_scope({**source, 'metadata': {'parser_strategy': 'second'}},
                           request, ['https://fixture.invalid/'])
    assert first != second


def test_background_scan_retains_generation_and_restarts_on_parser_change(monkeypatch):
    monkeypatch.setenv("CARSCANNER_MAX_PAGES_PER_SOURCE", "1")
    monkeypatch.setattr("src.source_adapters.adapter_execution_allowed", lambda _: True)
    monkeypatch.setattr("src.source_adapters.record_adapter_execution", lambda *a, **kw: None)
    monkeypatch.setattr("src.source_adapters.parse_live_listings", lambda *a: [])
    monkeypatch.setattr("src.source_adapters.parse_visible_listing_links", lambda *a: [])
    visited = []
    def fetch(url):
        visited.append(url)
        return '<a rel="next" href="?page=2">Next</a>' if '?' not in url else '<p>End of advertised links</p>'
    monkeypatch.setattr("src.source_adapters.fetch_text", fetch)
    source = {"name": "Fixture", "url": "https://fixture.invalid/", "parser_version": "v1"}
    first = BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(continuation={}))
    assert first.continuation and first.scan_evidence['terminal_reason'] == 'pending_pages'
    second = BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(continuation=first.continuation))
    assert second.continuation is None
    assert second.scan_evidence['generation_id'] == first.scan_evidence['generation_id']
    assert second.scan_evidence['coverage_state'] == 'traversal_exhausted_unverified'
    assert not second.scan_evidence['absence_reconciliation_permitted']
    changed = BuiltinMarketplaceAdapter({**source, 'parser_version': 'v2'}).fetch(AdapterRequest(continuation=first.continuation))
    assert visited[-1] == source['url']
    assert changed.scan_evidence['generation_id'] != first.scan_evidence['generation_id']
    for invalid in ({**first.continuation['scan_generation'], 'contract_version': 999},
                    {**first.continuation['scan_generation'], 'generation_id': None},
                    {**first.continuation['scan_generation'], 'started_at': None}, {}):
        incompatible = {**first.continuation, 'scan_generation': invalid}
        restarted = BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(continuation=incompatible))
        assert visited[-1] == source['url']
        assert restarted.scan_evidence['generation_id'] != first.scan_evidence['generation_id']
        assert not restarted.scan_evidence['resumed_legacy_checkpoint']
    legacy = {key: value for key, value in first.continuation.items() if key != 'scan_generation'}
    resumed = BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(continuation=legacy))
    assert visited[-1].endswith('?page=2')
    assert resumed.scan_evidence['resumed_legacy_checkpoint']
    assert not resumed.scan_evidence['completeness_verified']


def test_partial_failure_does_not_publish_success_evidence(monkeypatch):
    monkeypatch.setattr("src.source_adapters.adapter_execution_allowed", lambda _: True)
    monkeypatch.setattr("src.source_adapters.record_adapter_execution", lambda *a, **kw: None)
    monkeypatch.setattr("src.source_adapters.parse_live_listings", lambda *a: [])
    monkeypatch.setattr("src.source_adapters.parse_visible_listing_links", lambda *a: [])
    def fetch(url):
        if url.endswith('/second'):
            raise TimeoutError('source timeout')
        return '<p>First page</p>'
    monkeypatch.setattr("src.source_adapters.fetch_text", fetch)
    result = BuiltinMarketplaceAdapter({'name': 'Fixture', 'url': 'https://fixture.invalid/',
        'endpoints': [{'url': 'https://fixture.invalid/second'}]}).fetch(AdapterRequest(continuation={}))
    assert result.status != 'live'
    assert not result.scan_evidence
