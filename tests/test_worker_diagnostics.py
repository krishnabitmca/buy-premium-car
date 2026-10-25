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

    def test_missing_log_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = extract_summary(Path(tmp) / "missing", Path(tmp) / "out.json")
            self.assertEqual(report["status"], "no_log")


if __name__ == "__main__":
    unittest.main()
