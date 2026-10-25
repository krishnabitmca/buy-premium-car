"""A partially failed scheduled refresh must never appear green."""
import sys
import unittest
from unittest.mock import patch

from src import inventory_refresh_worker


class RefreshExitStatusTests(unittest.TestCase):
    def test_partial_failure_returns_nonzero(self):
        with patch.object(sys, "argv", ["inventory_refresh_worker"]), \
             patch.object(inventory_refresh_worker, "require_database"), \
             patch.object(inventory_refresh_worker, "run_batch",
                          return_value={"completed": 2, "failed": 1}):
            with self.assertRaises(SystemExit) as exc:
                inventory_refresh_worker.main()
        self.assertEqual(exc.exception.code, 1)

    def test_complete_failure_returns_nonzero(self):
        with patch.object(sys, "argv", ["inventory_refresh_worker"]), \
             patch.object(inventory_refresh_worker, "require_database"), \
             patch.object(inventory_refresh_worker, "run_batch",
                          return_value={"completed": 0, "failed": 3}):
            with self.assertRaises(SystemExit) as exc:
                inventory_refresh_worker.main()
        self.assertEqual(exc.exception.code, 1)

    def test_no_failure_exits_normally(self):
        with patch.object(sys, "argv", ["inventory_refresh_worker"]), \
             patch.object(inventory_refresh_worker, "require_database"), \
             patch.object(inventory_refresh_worker, "run_batch",
                          return_value={"completed": 0, "failed": 0}):
            inventory_refresh_worker.main()


    def test_failed_source_name_is_visible_without_control_characters(self):
        job = {"refresh_id": 62552, "source_name": "Quikr" + chr(10) + "Injected/Name"}
        with (patch.object(inventory_refresh_worker, "recover_jobs"),
              patch.object(inventory_refresh_worker, "claim_jobs", return_value=[job]),
              patch.object(inventory_refresh_worker, "process_job",
                           side_effect=RuntimeError("parser failed"))):
            with self.assertLogs(inventory_refresh_worker.log, level="ERROR") as captured:
                result = inventory_refresh_worker.run_batch(limit=1, workers=1)
        self.assertEqual(result["failed"], 1)
        self.assertIn("source=Quikr_Injected_Name", captured.output[0])
        self.assertNotIn("source=Quikr" + chr(10), captured.output[0])

    def test_safe_source_label_is_bounded_and_never_empty(self):
        self.assertEqual(inventory_refresh_worker._safe_source_label(None), "unknown")
        self.assertEqual(len(inventory_refresh_worker._safe_source_label("x" * 500)), 80)

if __name__ == "__main__":
    unittest.main()
