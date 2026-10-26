import json
import tempfile
import unittest
from pathlib import Path
from scripts.summarize_refresh_log import extract_summary, MAX_EVENTS, MAX_BYTES


class WorkerDiagnosticsTests(unittest.TestCase):
    def _run(self, lines):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "worker.log", Path(tmp) / "evidence.json"
            source.write_text("".join(lines), encoding="utf-8")
            result = extract_summary(source, output)
            return result, output.read_bytes()

    def test_allowlisted_aggregates_no_raw_errors_or_urls(self):
        telemetry = {"pages_traced": 2, "pages_empty": 1,
                     "pages_recovered_by_fallback": 1, "records_extracted": 3,
                     "strategy_attempts": {"html": 2}, "parser_errors": {"secret-token": 4},
                     "absence_reconciliation_permitted": False}
        line = ("INFO:src.inventory_refresh_worker:source_extraction_summary "
                "source=OEM Cars refresh_id=23 telemetry=" + json.dumps(telemetry) + "\n")
        report, raw = self._run([line])
        self.assertEqual(report["events_exported"], 1)
        self.assertEqual(report["events"][0]["records_extracted"], 3)
        self.assertEqual(report["events"][0]["parser_error_count"], 4)
        self.assertNotIn(b"secret-token", raw)
        self.assertNotIn(b"html", raw)
        self.assertFalse(report["absence_reconciliation_permitted"])

    def test_malformed_and_unsafe_events_rejected(self):
        line = ("source_extraction_summary source=Dealer refresh_id=4 telemetry="
                + json.dumps({"pages_traced": 1, "pages_empty": 0,
                    "pages_recovered_by_fallback": 0, "records_extracted": 0,
                    "absence_reconciliation_permitted": True}) + "\n")
        report, _ = self._run([line])
        self.assertEqual(report["events_invalid"], 1)
        self.assertEqual(report["events_exported"], 0)

    def test_no_events_is_not_evidence_of_absence(self):
        report, raw = self._run(["nothing processed\n"])
        self.assertEqual(report["status"], "no_events")
        self.assertEqual(report["events_observed"], 0)
        self.assertFalse(json.loads(raw)["absence_reconciliation_permitted"])

    def test_bounded_events_and_json(self):
        line = ("source_extraction_summary source=Dealer refresh_id=4 telemetry="
                + json.dumps({"pages_traced": 1, "pages_empty": 0,
                    "pages_recovered_by_fallback": 0, "records_extracted": 0,
                    "strategy_attempts": {}, "parser_errors": {},
                    "absence_reconciliation_permitted": False}) + "\n")
        report, raw = self._run([line] * (MAX_EVENTS + 30))
        self.assertEqual(report["events_exported"], MAX_EVENTS)
        self.assertEqual(report["events_omitted"], 30)
        self.assertLessEqual(len(raw), MAX_BYTES + 1)
        json.loads(raw)

    def test_committed_counts_distinguish_untraced_inventory_from_empty_source(self):
        telemetry = {"pages_traced": 0, "pages_empty": 0,
                     "pages_recovered_by_fallback": 0, "records_extracted": 0,
                     "pages_fetched": 3, "listings_extracted": 18,
                     "listings_ingested": 17, "strategy_attempts": {},
                     "parser_errors": {}, "absence_reconciliation_permitted": False}
        report, raw = self._run([
            "source_extraction_summary source=OEM Dealer refresh_id=7 telemetry="
            + json.dumps(telemetry) + "\n"
        ])
        self.assertEqual(report["events_exported"], 1)
        self.assertTrue(report["events"][0]["committed_metrics_available"])
        self.assertEqual(report["events"][0]["listings_ingested"], 17)
        self.assertEqual(report["events"][0]["pages_traced"], 0)
        self.assertFalse(json.loads(raw)["absence_reconciliation_permitted"])

    def test_partial_committed_metrics_are_not_exported(self):
        telemetry = {"pages_traced": 0, "pages_empty": 0,
                     "pages_recovered_by_fallback": 0, "records_extracted": 0,
                     "pages_fetched": 3, "strategy_attempts": {},
                     "parser_errors": {}, "absence_reconciliation_permitted": False}
        report, _ = self._run([
            "source_extraction_summary source=OEM refresh_id=7 telemetry="
            + json.dumps(telemetry) + "\n"
        ])
        self.assertEqual(report["events_invalid"], 1)
        self.assertEqual(report["events_exported"], 0)

    def test_zero_yield_oem_is_flagged_without_claiming_absence(self):
        telemetry = {"pages_traced": 0, "pages_empty": 0,
                     "pages_recovered_by_fallback": 0, "records_extracted": 0,
                     "pages_fetched": 10, "listings_extracted": 0,
                     "listings_ingested": 0, "strategy_attempts": {},
                     "parser_errors": {}, "absence_reconciliation_permitted": False}
        report, raw = self._run([
            "source_extraction_summary source=OEM refresh_id=9 telemetry="
            + json.dumps(telemetry) + "\n"
        ])
        flags = report["events"][0]["quality_flags"]
        self.assertIn("zero_yield_after_fetch", flags)
        self.assertIn("untraced_fetched_pages", flags)
        self.assertNotIn("parser_records_unaccepted", flags)
        self.assertEqual(report["quality_flag_counts"]["zero_yield_after_fetch"], 1)
        self.assertFalse(json.loads(raw)["absence_reconciliation_permitted"])

    def test_parser_record_rejected_is_distinguished_from_empty_source(self):
        telemetry = {"pages_traced": 1, "pages_empty": 0,
                     "pages_recovered_by_fallback": 1, "records_extracted": 1,
                     "pages_fetched": 1, "listings_extracted": 0,
                     "listings_ingested": 0, "strategy_attempts": {"fallback": 1},
                     "parser_errors": {}, "absence_reconciliation_permitted": False}
        report, raw = self._run([
            "source_extraction_summary source=9th Gear refresh_id=66900 telemetry="
            + json.dumps(telemetry) + "\n"
        ])
        flags = report["events"][0]["quality_flags"]
        self.assertIn("parser_records_unaccepted", flags)
        self.assertIn("zero_yield_after_fetch", flags)
        self.assertNotIn("untraced_fetched_pages", flags)
        self.assertNotIn(b"fallback", raw)

    def test_committed_ingestion_gap_is_flagged_but_successful_scan_is_not(self):
        base = {"pages_traced": 1, "pages_empty": 0,
                "pages_recovered_by_fallback": 0, "records_extracted": 4,
                "pages_fetched": 1, "listings_extracted": 4,
                "listings_ingested": 3, "strategy_attempts": {},
                "parser_errors": {}, "absence_reconciliation_permitted": False}
        good = {**base, "listings_ingested": 4}
        lines = [
            "source_extraction_summary source=Dealer refresh_id=1 telemetry=" + json.dumps(base) + "\n",
            "source_extraction_summary source=Dealer refresh_id=2 telemetry=" + json.dumps(good) + "\n",
        ]
        report, _ = self._run(lines)
        self.assertIn("extracted_not_ingested", report["events"][0]["quality_flags"])
        self.assertEqual(report["events"][1]["quality_flags"], [])
        self.assertEqual(report["quality_flag_counts"]["extracted_not_ingested"], 1)

    def test_legacy_trace_only_is_not_mislabeled_as_zero_yield(self):
        telemetry = {"pages_traced": 1, "pages_empty": 1,
                     "pages_recovered_by_fallback": 0, "records_extracted": 0,
                     "strategy_attempts": {}, "parser_errors": {},
                     "absence_reconciliation_permitted": False}
        report, _ = self._run([
            "source_extraction_summary source=Legacy refresh_id=3 telemetry="
            + json.dumps(telemetry) + "\n"
        ])
        self.assertEqual(report["events"][0]["quality_flags"], [])
        self.assertFalse(report["events"][0]["committed_metrics_available"])

    def test_missing_log_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = extract_summary(Path(tmp) / "missing", Path(tmp) / "out.json")
            self.assertEqual(report["status"], "no_log")

    def test_scheduled_refresh_requires_production_database(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/persistent-inventory-refresh.yml").read_text()
        # A scheduled production refresh must not silently mutate a test DB.
        self.assertEqual(
            workflow.count("SOURCE_INTELLIGENCE_DATABASE_URL: ${{ secrets.SOURCE_INTELLIGENCE_DATABASE_URL }}"),
            2,
        )
        self.assertNotIn("secrets.CARSCANNER_FREE_TEST_DATABASE_URL", workflow)
        self.assertIn('if [ -z "$SOURCE_INTELLIGENCE_DATABASE_URL" ]; then', workflow)
        self.assertIn("exit 1", workflow)
        self.assertIn("refusing to refresh a test database", workflow)

if __name__ == "__main__":
    unittest.main()
