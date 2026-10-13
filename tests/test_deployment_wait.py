import io
import json
import pytest
from scripts import wait_for_deployment as release


def test_release_wait_rejects_old_commit_and_accepts_expected(monkeypatch):
    calls = []
    commits = iter(['a' * 40, 'b' * 40])
    def open_response(request, timeout):
        calls.append(request.full_url)
        return io.BytesIO(json.dumps({'ok': True, 'commit': next(commits)}).encode())
    monkeypatch.setattr(release.urllib.request, 'urlopen', open_response)
    monkeypatch.setattr(release.time, 'sleep', lambda _: None)
    release.wait('https://fixture.invalid', 'b' * 40, timeout=5)
    assert calls == ['https://fixture.invalid/api/version'] * 2


def test_release_wait_has_a_deadline_and_rejects_invalid_sha(monkeypatch):
    with pytest.raises(ValueError): release.wait('https://fixture.invalid', 'not-a-commit')
    with pytest.raises(RuntimeError, match='deadline'): release.wait('https://fixture.invalid', 'a' * 40, timeout=0)
