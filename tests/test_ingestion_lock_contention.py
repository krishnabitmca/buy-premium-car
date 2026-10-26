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
            {"deferred": 1, "deferred_ingestion_lock": 1},
        )
        sql, params = cur.execute.call_args.args
        self.assertIn("status='queued'", sql)
        self.assertIn("attempt_count=greatest(0, attempt_count-1)", sql)
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

    def test_domain_lease_deferral_fences_exact_claim_timestamp(self):
        source = {"source_id": 19, "adapter_status": "live",
                  "url": "https://dealer.example", "name": "Verified Dealer"}
        conn = MagicMock()
        conn.__enter__.return_value = conn
        with (patch.object(worker, "load_registry", return_value=[source]),
              patch.object(worker, "_connect", return_value=conn),
              patch("src.crawl_leases.acquire", return_value=None),
              patch("src.crawl_leases.release")):
            result = worker.process_job(self.job)
        self.assertEqual(result, {"deferred": 1, "deferred_domain_lease": 1})
        sql, params = conn.execute.call_args.args
        self.assertIn("started_at=%s", sql)
        self.assertEqual(params, (7849, 2, self.job["started_at"]))
        conn.commit.assert_called_once()

    def test_dict_row_contention_is_deferred(self):
        # psycopg connections in production return dict_row, not tuple rows.
        source = {"source_id": 19, "adapter_status": "live",
                  "url": "https://dealer.example", "name": "Verified Dealer"}
        fetched = SimpleNamespace(
            status="live", listings=[], discovered_models=[{"model": "X1", "discovery_kind": "observed_model", "evidence_url": "https://dealer.example/x1"}], tombstones=[],
            pages_fetched=1, scan_evidence={}, continuation=None,
        )
        cur = MagicMock()
        cur.fetchone.return_value = {"acquired": False}
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
              patch("src.crawl_leases.release"),
              patch("src.used_inventory_frontier.enqueue_models") as enqueue):
            adapter.return_value.fetch.return_value = fetched
            result = worker.process_job(self.job)
        self.assertEqual(result, {"deferred": 1, "deferred_ingestion_lock": 1})
        ingest.assert_not_called()
        complete.assert_not_called()
        enqueue.assert_not_called()

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
        self.assertEqual(result, {"deferred": 1, "deferred_ingestion_lock": 1})
        self.assertIn("pg_try_advisory_xact_lock", cur.execute.call_args_list[0].args[0])
        ingest.assert_not_called()
        complete.assert_not_called()
        conn.commit.assert_called_once()


    def test_batch_reports_deferral_reasons_without_changing_failure_semantics(self):
        jobs = [{"refresh_id": 1}, {"refresh_id": 2}, {"refresh_id": 3}]
        outcomes = [
            {"deferred": 1, "deferred_domain_lease": 1},
            {"deferred": 1, "deferred_ingestion_lock": 1},
            {"listings": 1, "pages_fetched": 1, "listings_extracted": 1},
        ]
        with (patch.object(worker, "recover_jobs"),
              patch.object(worker, "claim_jobs", side_effect=[[job] for job in jobs]),
              patch.object(worker, "process_job", side_effect=outcomes)):
            summary = worker.run_batch(limit=3, workers=1)
        self.assertEqual(summary["deferred"], 2)
        self.assertEqual(summary["deferred_domain_lease"], 1)
        self.assertEqual(summary["deferred_ingestion_lock"], 1)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertNotIn("source_name", summary)


    def test_successful_claim_enqueues_models_in_same_transaction(self):
        source = {"source_id": 19, "adapter_status": "live",
                  "url": "https://dealer.example", "name": "Verified Dealer"}
        models = [{"model": "X1", "discovery_kind": "observed_model",
                   "evidence_url": "https://dealer.example/x1"}]
        fetched = SimpleNamespace(
            status="live", listings=[], discovered_models=models, tombstones=[],
            pages_fetched=1, scan_evidence={}, continuation=None,
        )
        job = {**self.job, "brand": "BMW"}
        cur = MagicMock()
        cur.fetchone.side_effect = [{"acquired": True}, {"refresh_id": 7849}]
        cur.__enter__.return_value = cur
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value = cur

        def check_in_transaction(*args, **kwargs):
            self.assertFalse(conn.commit.called, "model discovery must precede ingestion commit")
            self.assertIs(kwargs.get('_connection'), conn)
            return 1

        with (patch.object(worker, "load_registry", return_value=[source]),
              patch.object(worker, "BuiltinMarketplaceAdapter") as adapter,
              patch.object(worker, "_connect", return_value=conn),
              patch.object(worker, "ingest_vehicles", return_value={"listings": 0}),
              patch.object(worker, "complete_job") as complete,
              patch("src.crawl_leases.acquire", return_value=object()),
              patch("src.crawl_leases.release"),
              patch("src.used_inventory_frontier.enqueue_models",
                    side_effect=check_in_transaction) as enqueue):
            adapter.return_value.fetch.return_value = fetched
            result = worker.process_job(job)
        self.assertEqual(result["pages_fetched"], 1)
        enqueue.assert_called_once_with("BMW", models, _connection=conn)
        complete.assert_called_once()


    def test_discovery_enqueue_failure_cannot_commit_inventory(self):
        source = {"source_id": 19, "adapter_status": "live",
                  "url": "https://dealer.example", "name": "Verified Dealer"}
        models = [{"model": "X1", "discovery_kind": "observed_model",
                   "evidence_url": "https://dealer.example/x1"}]
        fetched = SimpleNamespace(
            status="live", listings=[], discovered_models=models, tombstones=[],
            pages_fetched=1, scan_evidence={}, continuation=None,
        )
        cur, conn = MagicMock(), MagicMock()
        cur.fetchone.side_effect = [{"acquired": True}, {"refresh_id": 7849}]
        cur.__enter__.return_value = cur
        conn.__enter__.return_value = conn
        conn.cursor.return_value = cur
        with (patch.object(worker, "load_registry", return_value=[source]),
              patch.object(worker, "BuiltinMarketplaceAdapter") as adapter,
              patch.object(worker, "_connect", return_value=conn),
              patch.object(worker, "ingest_vehicles", return_value={"listings": 0}),
              patch.object(worker, "complete_job") as complete,
              patch("src.crawl_leases.acquire", return_value=object()),
              patch("src.crawl_leases.release"),
              patch("src.used_inventory_frontier.enqueue_models",
                    side_effect=RuntimeError("transient queue failure"))):
            adapter.return_value.fetch.return_value = fetched
            with self.assertRaisesRegex(RuntimeError, "transient queue failure"):
                worker.process_job({**self.job, "brand": "BMW"})
        conn.commit.assert_not_called()
        complete.assert_called_once()
        self.assertFalse(complete.call_args.kwargs["success"])



if __name__ == "__main__":
    unittest.main()
