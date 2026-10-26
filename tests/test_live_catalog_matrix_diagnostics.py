"""Regression tests for the live catalog matrix's zero-match classifications."""

import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _classifier():
    # Load the diagnostic script without importing the real network-backed
    # marketplace module or executing its main() function.
    fake = types.ModuleType("src.live_marketplaces")
    fake.live_brands = lambda: []
    fake.live_models = lambda brand: []
    fake.live_inventory = lambda query: ([], [])
    script = Path(__file__).with_name("live_catalog_matrix.py")
    with patch.dict(sys.modules, {"src.live_marketplaces": fake}):
        return runpy.run_path(str(script))["classify_zero_matches"]


class LiveMatrixZeroMatchTests(unittest.TestCase):
    def test_empty_supply_from_live_sources_is_not_identity_mismatch(self):
        classify = _classifier()
        rows = [{"status": "ok", "matched": 0, "vehicles": 0, "live_sources": 12}]
        zero, actionable = classify(rows)
        self.assertEqual(zero, rows)
        self.assertEqual(actionable, [])

    def test_nonempty_supply_without_identity_match_is_actionable(self):
        classify = _classifier()
        rows = [{"status": "ok", "matched": 0, "vehicles": 4, "live_sources": 2}]
        zero, actionable = classify(rows)
        self.assertEqual(zero, rows)
        self.assertEqual(actionable, rows)

    def test_matching_and_failed_probes_do_not_count_as_zero_matches(self):
        classify = _classifier()
        rows = [
            {"status": "ok", "matched": 1, "vehicles": 1, "live_sources": 1},
            {"status": "error", "matched": 0, "vehicles": 0, "live_sources": 0},
        ]
        self.assertEqual(classify(rows), ([], []))


if __name__ == "__main__":
    unittest.main()
