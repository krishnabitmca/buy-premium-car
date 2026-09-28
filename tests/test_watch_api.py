from types import SimpleNamespace

import pytest

from api import watch


def test_access_token_hash_is_one_way_shape():
    token = "test-private-token"
    digest = watch._token_hash(token)
    assert digest == watch._token_hash(token)
    assert digest != token
    assert len(digest) == 64


def test_auth_token_prefers_bearer_header():
    fake = SimpleNamespace(
        headers={"Authorization": "Bearer abc123"},
        path="/api/watch?token=query-token",
    )
    assert watch._auth_token(fake) == "abc123"


def test_auth_token_accepts_query_fallback():
    fake = SimpleNamespace(
        headers={},
        path="/api/watch?token=query-token",
    )
    assert watch._auth_token(fake) == "query-token"


def test_email_filter_is_url_encoded(monkeypatch):
    captured = {}

    def fake_request(method, path, payload=None, prefer=None):
        captured["method"] = method
        captured["path"] = path
        return [{"user_id": "u1"}]

    monkeypatch.setattr(watch, "_supabase_request", fake_request)
    rows = watch._find_user_by_email("person+car@example.com")
    assert rows["user_id"] == "u1"
    assert "person%2Bcar%40example.com" in captured["path"]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("9876543210", "+919876543210"),
        ("09876543210", "+919876543210"),
        ("+919876543210", "+919876543210"),
    ],
)
def test_phone_normalization(value, expected):
    assert watch._phone_e164(value) == expected


def test_new_watch_requires_private_access_for_existing_claimed_email(monkeypatch):
    class Row:
        def __init__(self, data):
            self.data = data
        def get(self, key, default=None):
            return self.data.get(key, default)
        def __getitem__(self, key):
            return self.data[key]

    monkeypatch.setattr(
        watch,
        "_find_user_by_token",
        lambda token: None,
    )
    monkeypatch.setattr(
        watch,
        "_find_user_by_email",
        lambda email: {
            "user_id": "u1",
            "email": email,
            "phone_e164": None,
            "status": "active",
            "access_token_hash": "already-set",
        },
    )
    assert watch._find_user_by_email("x@example.com")["access_token_hash"] == "already-set"
