"""Historical sample fidelity, drift and fail-closed artifact contracts."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src import parser_replay as replay

HTML = Path('tests/fixtures/reviewed_fusion.html').read_text(encoding='utf-8')
BASE = 'https://fusioncars.in/collections/'
STAMP = datetime(2026, 10, 20, tzinfo=timezone.utc)


def sample(html=HTML, **kwargs):
    return replay.capture_sample(html, source_url=BASE, captured_at=STAMP, **kwargs)


def test_real_parser_positive_fields_and_explicit_sold_survive_sanitization():
    artifact = sample()
    assert artifact['sample_count'] == 4
    assert artifact['selection_limited'] is False
    expected = replay._extract(HTML, 'Fusion Cars', BASE, artifact['brand_names'])
    assert artifact['expected'] == expected
    assert len(expected['positive']) == 3
    assert len(expected['explicit_negative']) == 1
    first = expected['positive'][0]
    assert first['price_lakh'] == 210
    assert first['km'] == 6000
    assert first['registration_year'] == 2024
    assert first['condition_signal'] == 'used'
    sold_url = expected['explicit_negative'][0]['url']
    assert all(row['url'].rstrip('/') != sold_url for row in expected['positive'])
    result = replay.replay_sample(artifact)
    assert result['status'] == 'matched'
    assert (result['positive_count'], result['negative_count']) == (3, 1)


def test_deterministic_serialization_and_operator_generation_reference():
    generation = '53377108-7ad5-5e82-8584-7f0aad9d9944'
    a = sample(scan_generation=generation, brand_names=['BMW', 'Mercedes Benz'])
    b = sample(scan_generation=generation, brand_names=['Mercedes Benz', 'BMW', 'BMW'])
    assert a == b
    assert a['scan_generation'] == generation
    assert a['captured_at'] == STAMP.isoformat()
    assert a['input_sha256'] == sha256(HTML.encode()).hexdigest()
    assert replay.replay_sample(a)['absence_reconciliation_permitted'] is False


def test_five_card_sample_never_claims_catalogue_completeness():
    artifact = sample(HTML * 3)
    assert artifact['status'] == 'captured_sample'
    assert artifact['sample_count'] == 5
    assert artifact['selection_limited'] is True
    assert len(BeautifulSoup(artifact['html'], 'html.parser').select('.product')) == 5
    assert artifact['completeness_verified'] is False
    assert replay.replay_sample(artifact)['status'] == 'matched'


def test_current_parser_field_change_is_reported_as_historical_drift(monkeypatch):
    artifact = sample()
    original = replay.parse_reviewed_cards

    def changed(*args, **kwargs):
        rows = original(*args, **kwargs)
        rows[0]['price_lakh'] += 1
        return rows

    monkeypatch.setattr(replay, 'parse_reviewed_cards', changed)
    result = replay.replay_sample(artifact)
    assert result['status'] == 'drift'
    assert result['historical_sample'] is True
    assert result['absence_reconciliation_permitted'] is False
    assert 'expected' not in result and 'html' not in result


@pytest.mark.parametrize('field,value', [
    ('version', True), ('version', 999), ('parser_version', 'future'),
    ('sanitizer_version', 'future'), ('strategy', 'unreviewed'),
    ('sample_count', True), ('sample_count', 6), ('selection_limited', 1),
    ('historical_sample', False), ('sampled_only', False),
    ('completeness_verified', True), ('absence_reconciliation_permitted', True),
    ('source_url', 'https://unreviewed.invalid/collections/'),
    ('captured_at', '2026-10-20T12:00:00'), ('scan_generation', 'not-a-uuid'),
    ('brand_names', ['Private secret brand']), ('html_sha256', '0' * 64),
    ('input_sha256', 'not-a-hash'), ('expected_sha256', '0' * 64),
])
def test_invalid_artifact_metadata_fails_closed(field, value):
    artifact = sample()
    artifact[field] = value
    assert replay.replay_sample(artifact)['status'] == 'replay_unavailable'


def test_tampered_html_rejected_even_when_its_hash_is_recomputed():
    artifact = sample()
    artifact['html'] += '<script>private_session="secret"</script>'
    artifact['html_sha256'] = sha256(artifact['html'].encode()).hexdigest()
    result = replay.replay_sample(artifact)
    assert result['status'] == 'replay_unavailable'
    assert 'secret' not in json.dumps(result)


def test_changed_expected_values_with_valid_hash_report_drift_without_echo():
    artifact = deepcopy(sample())
    artifact['expected']['positive'][0]['model'] = 'private-untrusted-value'
    artifact['expected_sha256'] = sha256(replay._encoded(artifact['expected'])).hexdigest()
    result = replay.replay_sample(artifact)
    assert result['status'] == 'drift'
    assert 'private-untrusted-value' not in json.dumps(result)


@pytest.mark.parametrize('html', ['', '<h1>Verify you are human</h1>', '<div>No cars</div>'])
def test_empty_or_challenge_input_is_unavailable_evidence_not_a_complete_scan(html):
    artifact = sample(html)
    assert artifact['status'] == 'no_supported_cards'
    assert artifact['absence_reconciliation_permitted'] is False
    assert 'html' not in artifact


def test_unsupported_strategy_and_serialized_size_cap(monkeypatch):
    assert sample(strategy='unreviewed')['status'] == 'unsupported_strategy'
    monkeypatch.setattr(replay, 'MAX_ARTIFACT_BYTES', 128)
    assert sample()['status'] == 'sample_oversized'


def test_parser_failure_restores_brand_context(monkeypatch):
    previous = ('Previous Context',)
    token = replay.lm._brand_identity_snapshot.set(previous)

    def fail(*args, **kwargs):
        raise ValueError('Parser failure')

    monkeypatch.setattr(replay, 'parse_reviewed_cards', fail)
    try:
        with pytest.raises(ValueError):
            sample()
        assert replay.lm._brand_identity_snapshot.get() == previous
    finally:
        replay.lm._brand_identity_snapshot.reset(token)


def test_sanitizable_cards_without_parser_evidence_do_not_create_vacuous_match(monkeypatch):
    monkeypatch.setattr(replay, 'parse_reviewed_cards', lambda *args: [])
    monkeypatch.setattr(replay, 'catalogue_tombstones', lambda *args: [])
    artifact = sample()
    assert artifact['status'] == 'no_supported_cards'
    assert 'html' not in artifact
    assert artifact['completeness_verified'] is False


@pytest.mark.parametrize('slug', ['api-key-private', 'csrf-private', 'cookie-private', 'contact-private'])
def test_credential_or_contact_paths_are_not_retained(slug):
    html = HTML.replace('2023-24-mercedes-benz-sl55-amg-2', slug)
    artifact = sample(html)
    assert artifact['status'] == 'no_supported_cards'
    assert slug not in json.dumps(artifact)


@pytest.mark.parametrize('stamp', ['', False, 0, None, [], {}])
def test_artifact_timestamp_cannot_default_to_now(stamp):
    artifact = sample()
    artifact['captured_at'] = stamp
    assert replay.replay_sample(artifact)['status'] == 'replay_unavailable'


@pytest.mark.parametrize('stamp', ['', False, 0, [], {}])
def test_capture_rejects_falsy_timestamps_other_than_none(stamp):
    with pytest.raises(ValueError):
        replay.capture_sample(HTML, source_url=BASE, captured_at=stamp)


def test_total_extraction_loss_is_drift_for_a_valid_historical_sample(monkeypatch):
    artifact = sample()
    monkeypatch.setattr(replay, 'parse_reviewed_cards', lambda *args: [])
    monkeypatch.setattr(replay, 'catalogue_tombstones', lambda *args: [])
    result = replay.replay_sample(artifact)
    assert result['status'] == 'drift'
    assert result['positive_count'] == result['negative_count'] == 0
    assert result['absence_reconciliation_permitted'] is False


@pytest.mark.parametrize('error', [RuntimeError, IndexError])
def test_unexpected_parser_errors_are_sanitized_and_restore_context(monkeypatch, error):
    artifact = sample()
    def fail(*args):
        raise error('token=private-parser-error')
    token = replay.lm._brand_identity_snapshot.set(('Previous Context',))
    monkeypatch.setattr(replay, 'parse_reviewed_cards', fail)
    try:
        result = replay.replay_sample(artifact)
        assert result['status'] == 'replay_unavailable'
        assert 'private-parser-error' not in json.dumps(result)
        assert replay.lm._brand_identity_snapshot.get() == ('Previous Context',)
    finally:
        replay.lm._brand_identity_snapshot.reset(token)
