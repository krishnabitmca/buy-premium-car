"""Scheduled lifecycle failures must leave a bounded, uploadable report."""
import json
import sys

import pytest

from src import inventory_lifecycle as lifecycle


@pytest.mark.parametrize("failure_stage,exception_type", [
    ("run_cycle", RuntimeError),
    ("report", TimeoutError),
])
def test_lifecycle_failure_preserves_exit_and_writes_safe_artifact(
    monkeypatch, tmp_path, failure_stage, exception_type
):
    path = tmp_path / "coverage" / "inventory-lifecycle.json"
    monkeypatch.setattr(sys, "argv", ["inventory_lifecycle", "--limit", "10", "--report", str(path)])
    monkeypatch.setattr(lifecycle, "run_cycle", lambda limit: {"heartbeat_gap_seconds": 0})
    monkeypatch.setattr(lifecycle, "report", lambda: {"offers": []})

    def fail(*args, **kwargs):
        raise exception_type("signed URL or database credentials must not leak")

    monkeypatch.setattr(lifecycle, failure_stage, fail)
    with pytest.raises(exception_type):
        lifecycle.main()
    evidence = json.loads(path.read_text(encoding="utf-8"))
    assert evidence == {
        "status": "failed",
        "stage": failure_stage,
        "fatal_error": exception_type.__name__,
    }
    assert "credentials" not in path.read_text(encoding="utf-8")


def test_successful_lifecycle_keeps_full_report(monkeypatch, tmp_path):
    path = tmp_path / "coverage" / "inventory-lifecycle.json"
    monkeypatch.setattr(sys, "argv", ["inventory_lifecycle", "--report", str(path)])
    monkeypatch.setattr(lifecycle, "run_cycle", lambda limit: {"heartbeat_gap_seconds": 0, "expired": 2})
    monkeypatch.setattr(lifecycle, "report", lambda: {"offers": [{"source": "fixture", "count": 2}]})
    lifecycle.main()
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "offers": [{"source": "fixture", "count": 2}]
    }
