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


def test_lifecycle_gap_tracks_previous_lifecycle_run_not_worker(monkeypatch):
    """The old heartbeat key is a compatibility alias, not a worker health signal."""
    from datetime import datetime, timedelta, timezone
    from unittest.mock import MagicMock

    previous = datetime.now(timezone.utc) - timedelta(hours=2)
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.return_value.fetchone.return_value = {"last_start": previous}
    monkeypatch.setattr(lifecycle, "_connect", lambda: connection)
    monkeypatch.setattr(lifecycle, "require_database", lambda: None)
    monkeypatch.setattr(lifecycle, "maintain", lambda: {"expired": 0})
    monkeypatch.setattr(lifecycle, "claim", lambda *args: None)

    summary = lifecycle.run_cycle(limit=1)
    assert 7190 <= summary["lifecycle_run_gap_seconds"] <= 7210
    assert summary["heartbeat_gap_seconds"] == summary["lifecycle_run_gap_seconds"]
    assert "degraded" in str(connection.execute.call_args_list)


def test_lifecycle_warning_does_not_claim_worker_heartbeat(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["inventory_lifecycle"])
    monkeypatch.setattr(lifecycle, "run_cycle", lambda limit: {
        "lifecycle_run_gap_seconds": 7200, "heartbeat_gap_seconds": 7200,
    })
    lifecycle.main()
    output = capsys.readouterr().out
    assert "lifecycle run gap exceeded one hour" in output.lower()
    assert "worker heartbeat" not in output.lower()
