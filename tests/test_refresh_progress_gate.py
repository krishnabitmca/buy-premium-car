"""Regression coverage for a scheduled worker that claims work but makes no progress."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from src import inventory_refresh_worker as worker


class RefreshProgressGateTests(unittest.TestCase):
    def run_cli(self, summary, *, enforce=True):
        argv = ["inventory_refresh_worker", "--limit", "80"]
        if enforce:
            argv.append("--fail-on-all-deferred")
        with (patch.object(sys, "argv", argv),
              patch.object(worker, "require_database"),
              patch.object(worker, "run_batch", return_value=summary)):
            return worker.main()

    def test_all_deferred_exits_nonzero(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli({"completed": 0, "failed": 0, "deferred": 80})
        self.assertEqual(ctx.exception.code, 2)

    def test_partial_progress_remains_successful(self):
        self.assertIsNone(self.run_cli({"completed": 1, "failed": 0, "deferred": 79}))

    def test_idle_queue_is_not_reported_as_stalled(self):
        self.assertIsNone(self.run_cli({"completed": 0, "failed": 0}))

    def test_existing_failure_exit_code_is_preserved(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli({"completed": 0, "failed": 1, "deferred": 1})
        self.assertEqual(ctx.exception.code, 1)

    def test_gate_is_opt_in_for_other_callers(self):
        self.assertIsNone(self.run_cli({"completed": 0, "failed": 0, "deferred": 80}, enforce=False))

    def test_persistent_workflow_enforces_gate_and_keeps_diagnostics(self):
        workflow = Path(".github/workflows/persistent-inventory-refresh.yml").read_text(encoding="utf-8")
        self.assertIn("--limit 80 --workers 4 --fail-on-all-deferred", workflow)
        self.assertIn("set -o pipefail", workflow)
        self.assertIn("tee /tmp/carscanner-refresh.log", workflow)
        self.assertIn("name: Publish bounded extraction diagnostics", workflow)
        self.assertIn("if: always()", workflow)


if __name__ == "__main__":
    unittest.main()
