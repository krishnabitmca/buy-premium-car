"""Advisory-lock contention must not turn a valid crawl into a failed source."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src import inventory_refresh_worker as worker


class IngestionLockContentionTests(unittest.TestCase):
    def setUp(self):
        self.job = {
            "refresh_id": 7849, "attempt_count": 2,
            "started_at": datetime(2026, 10, 25, tzinfo=timezone.utc),
            "source_name": "Verified Dealer", "source_id": 19,
            "brand": "", "model": "", "condition": "both",
            "destination_state": "", "metadata": {},
        }

    def test_deferral_is_fenced_and_preserves_attempt_budget(self):
        cur = MagicMock()
        cur.rowcount = 1
        conn = MagicMock()
        self.assertEqual(
            worker._defer_ingestion_on_lock_contention(cur, conn, self.job),
            {"deferred": 1},
        )
        sql, params = cur.execute.call_args.args
        self.assertIn("status='queued'", sql)
        self.assertIn("attempt_count=attempt_count-1", sql)
        self.assertIn("next_attempt_at", sql)
        self.assertIn("status='running'", sql)
        self.assertIn("started_at=%s", sql)
        self.assertEqual(params, (7849, 2, self.job["started_at"]))
        conn.commit.assert_called_once()

    def test_superseded_claim_is_not_requeued(self):
        cur, conn = MagicMock(), MagicMock()
        cur.rowcount = 0
        self.assertEqual(
            worker._defer_ingestion_on_lock_contention(cur, conn, self.job),
            {"superseded": 1},
        )
        conn.commit.assert_called_once()

    def test_lock_contention_skips_ingestion_and_deletion(self):
        source = {"source_id": 19, "adapter_status": "live",
                  "url": "https://dealer.example", "name": "Verified Dealer"}
        fetched = SimpleNamespace(
            status="live", listings=[], discovered_models=[], tombstones=[],
            pages_fetched=1, scan_evidence={}, continuation=None,
        )
        cur = MagicMock()
        cur.fetchone.return_value = (False,)
        cur.rowcount = 1
        cur.__enter__.return_value = cur
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value = cur
        with (patch.object(worker, "load_registry", return_value=[source]),
              patch.object(worker, "BuiltinMarketplaceAdapter") as adapter,
              patch.object(worker, "_connect", return_value=conn),
              patch.object(worker, "ingest_vehicles") as ingest,
              patch.object(worker, "complete_job") as complete,
              patch("src.crawl_leases.acquire", return_value=object()),
              patch("src.crawl_leases.release")):
            adapter.return_value.fetch.return_value = fetched
            result = worker.process_job(self.job)
        self.assertEqual(result, {"deferred": 1})
        self.assertIn("pg_try_advisory_xact_lock", cur.execute.call_args_list[0].args[0])
        ingest.assert_not_called()
        complete.assert_not_called()
        conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
