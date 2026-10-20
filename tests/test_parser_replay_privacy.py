"""Independent privacy/negative tests around the real Fusion parser replay."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from src import live_marketplaces as lm

FIXTURE = Path('tests/fixtures/reviewed_fusion.html').read_text(encoding='utf-8')
BASE = 'https://fusioncars.in/collections/'
TITLE = '2023/24 MERCEDES BENZ SL55 AMG'
LISTING = 'https://fusioncars.in/cars/2023-24-mercedes-benz-sl55-amg-2/'


def capture(html=FIXTURE, **kwargs):
    from src.parser_replay import capture_sample
    return capture_sample(html, source_url=BASE, **kwargs)


def replay(artifact):
    from src.parser_replay import replay_sample
    return replay_sample(artifact)


def serialized(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def test_rebuilt_artifact_drops_private_markup_and_image_attributes():
    body = FIXTURE.replace('<div class="car_heading">', '''
        <!-- session-secret-comment -->
        <script>window.token="script-secret"</script>
        <form><input name="csrf" value="form-secret"></form>
        <div class="car_heading" onclick="handler-secret" data-cookie="attribute-secret">''')
    body = body.replace('width="100%"', 'width="100%" data-secret="image-secret"')
    artifact = capture(body)
    assert artifact['status'] == 'captured_sample'
    text = serialized(artifact)
    for secret in ('session-secret-comment', 'script-secret', 'form-secret',
                   'handler-secret', 'attribute-secret', 'image-secret', 'WhatsApp-Image'):
        assert secret not in text
    assert replay(artifact)['status'] == 'matched'


@pytest.mark.parametrize('private_text', [
    'Call +91 9876543210', 'contact@example.com', 'token=buyer-secret',
    'session_id=private-session', 'Bearer abc-private-credential',
])
def test_private_freetext_is_not_retained_or_echoed(private_text):
    artifact = capture(FIXTURE.replace(TITLE, TITLE + ' ' + private_text))
    assert artifact['status'] != 'captured_sample'
    assert private_text not in serialized(artifact)


@pytest.mark.parametrize('unsafe', [
    'https://fusioncars.in/cars/stock/?token=private-query',
    'https://user:private-password@fusioncars.in/cars/stock/',
    'https://unreviewed.invalid/cars/stock/',
    'javascript:private-payload',
])
def test_unsafe_listing_url_never_enters_retained_artifact(unsafe):
    artifact = capture(FIXTURE.replace(LISTING, unsafe))
    assert artifact['status'] != 'captured_sample'
    assert unsafe not in serialized(artifact)


def test_input_byte_limit_is_enforced_before_parser(monkeypatch):
    from src import parser_replay
    def forbidden(*args, **kwargs):
        raise AssertionError('Oversized input must never reach the parser')
    monkeypatch.setattr(parser_replay, 'parse_reviewed_cards', forbidden)
    assert capture('x' * (1024 * 1024 + 1))['status'] == 'input_oversized'


def test_capture_and_replay_never_access_database_network_or_ingestion(monkeypatch):
    from src import parser_replay, source_registry_db, inventory_ingestion
    import urllib.request
    def forbidden(*args, **kwargs):
        pytest.fail('Historical parser replay must have no operational side effects')
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', forbidden)
    monkeypatch.setattr(lm, 'load_source_registry', forbidden)
    monkeypatch.setattr(source_registry_db, '_connect', forbidden)
    monkeypatch.setattr(inventory_ingestion, 'ingest_vehicles', forbidden)
    previous = ('Private Previous Context',)
    token = lm._brand_identity_snapshot.set(previous)
    try:
        artifact = capture()
        assert artifact['status'] == 'captured_sample'
        result = replay(artifact)
        assert result['status'] == 'matched'
        assert result['historical_sample'] is True
        assert lm._brand_identity_snapshot.get() == previous
    finally:
        lm._brand_identity_snapshot.reset(token)
    assert 'live_verified' not in serialized(artifact)
    assert 'availability_confirmed' not in serialized(result)


def test_replay_rejects_unknown_fields_without_echoing_them():
    artifact = capture()
    artifact['private_session'] = 'do-not-echo-this-secret'
    result = replay(artifact)
    assert result['status'] == 'replay_unavailable'
    assert 'do-not-echo-this-secret' not in serialized(result)


@pytest.mark.parametrize('malformed', [None, [], '', {'status': 'captured_sample'}])
def test_malformed_artifacts_fail_closed(malformed):
    result = replay(malformed)
    assert result['status'] == 'replay_unavailable'


def test_artifact_and_replay_results_cannot_grant_absence_authority():
    artifact = capture()
    assert artifact['status'] == 'captured_sample'
    for record in (artifact, replay(artifact)):
        assert record.get('completeness_verified') is False
        assert record.get('absence_reconciliation_permitted') is False
    tampered = deepcopy(artifact)
    tampered['absence_reconciliation_permitted'] = True
    assert replay(tampered)['status'] == 'replay_unavailable'
