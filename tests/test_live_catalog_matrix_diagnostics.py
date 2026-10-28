"""Regression tests for evidence-based live-matrix zero-match diagnostics."""
from pathlib import Path
from runpy import run_path


def _classify(rows):
    module = run_path(str(Path(__file__).with_name("live_catalog_matrix.py")))
    return module["_actionable_zero_matches"](rows)


def test_live_sources_without_returned_inventory_are_not_actionable():
    rows = [
        {"brand": "BMW", "model": "3 Series 2027", "status": "ok",
         "vehicles": 0, "matched": 0, "live_sources": 14},
        {"brand": "Audi", "model": "Q5", "status": "ok",
         "vehicles": 0, "matched": 0, "live_sources": 8},
    ]
    assert _classify(rows) == []


def test_returned_nonmatching_vehicles_are_actionable():
    mismatch = {"brand": "BMW", "model": "X5", "status": "ok",
                "vehicles": 3, "matched": 0, "live_sources": 4}
    healthy = {"brand": "BMW", "model": "X3", "status": "ok",
               "vehicles": 2, "matched": 2, "live_sources": 4}
    failed = {"brand": "BMW", "model": "X1", "status": "error",
              "vehicles": 2, "matched": 0, "live_sources": 4}
    assert _classify([mismatch, healthy, failed]) == [mismatch]


def test_unavailable_sources_do_not_change_vehicle_evidence_rule():
    mismatch = {"status": "ok", "vehicles": 1, "matched": 0, "live_sources": 0}
    assert _classify([mismatch]) == [mismatch]
