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


if __name__ == "__main__":
    unittest.main()
