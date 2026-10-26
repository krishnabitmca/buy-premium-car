"""Emit bounded, sanitized extraction evidence from a worker log.

Only allowlisted aggregate counts are exported. Raw logs, URLs, arbitrary parser
errors and other potentially sensitive strings never enter the artifact.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MAX_EVENTS = 200
MAX_BYTES = 64_000
SOURCE_PATTERN = re.compile(r"source=(.*?) refresh_id=([0-9]+) telemetry=")
METRICS = ("pages_traced", "pages_empty", "pages_recovered_by_fallback", "records_extracted")
COMMITTED_METRICS = ("pages_fetched", "listings_extracted", "listings_ingested")
# Investigation signals, not proof that a source has stock or that listings are sold.
QUALITY_FLAGS = ("zero_yield_after_fetch", "parser_records_unaccepted",
                 "extracted_not_ingested", "untraced_fetched_pages")


def extract_summary(log_path: Path, output_path: Path) -> dict:
    events = []
    observed = 0
    invalid = 0
    if log_path.is_file():
        with log_path.open("r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                if "source_extraction_summary " not in line:
                    continue
                observed += 1
                if len(events) >= MAX_EVENTS:
                    continue
                match = SOURCE_PATTERN.search(line)
                if not match:
                    invalid += 1
                    continue
                try:
                    payload = json.loads(line.split(" telemetry=", 1)[1])
                    if not isinstance(payload, dict):
                        raise ValueError("not a telemetry object")
                    counts = {key: payload[key] for key in METRICS}
                    if any(type(v) is not int or v < 0 for v in counts.values()):
                        raise ValueError("invalid count")
                    if payload.get("absence_reconciliation_permitted") is not False:
                        raise ValueError("unsafe absence reconciliation flag")
                    # Accept legacy trace-only logs, but never export a partial
                    # set of durable outcome counters as if it were complete.
                    committed_present = [key in payload for key in COMMITTED_METRICS]
                    if any(committed_present) and not all(committed_present):
                        raise ValueError("incomplete committed outcome counters")
                    committed = ({key: payload[key] for key in COMMITTED_METRICS}
                                 if all(committed_present) else {})
                    if any(type(v) is not int or v < 0 for v in committed.values()):
                        raise ValueError("invalid committed outcome counter")
                    source = re.sub(r"[^a-zA-Z0-9 ._/-]", "_", match.group(1))[:80]
                    if not source:
                        raise ValueError("missing source")
                    attempts = payload.get("strategy_attempts", {})
                    errors = payload.get("parser_errors", {})
                    if not isinstance(attempts, dict) or not isinstance(errors, dict):
                        raise ValueError("invalid category counters")
                    for counters in (attempts, errors):
                        if any(type(v) is not int or v < 0 for v in counters.values()):
                            raise ValueError("invalid category count")
                    # Only committed counts can distinguish a zero-yield scan
                    # from missing trace instrumentation. These are triage flags,
                    # never authoritative absence or deletion evidence.
                    flags = {
                        "zero_yield_after_fetch": bool(committed and committed["pages_fetched"] > 0
                                                       and committed["listings_extracted"] == 0),
                        "parser_records_unaccepted": bool(committed and counts["records_extracted"] > 0
                                                          and committed["listings_extracted"] == 0),
                        "extracted_not_ingested": bool(committed and committed["listings_extracted"] >
                                                       committed["listings_ingested"]),
                        "untraced_fetched_pages": bool(committed and committed["pages_fetched"] > 0
                                                       and counts["pages_traced"] == 0),
                    }
                    # Sparse flag names avoid exceeding the artifact cap when
                    # hundreds of healthy sources produce no investigation flags.
                    active_flags = [name for name in QUALITY_FLAGS if flags[name]]
                    events.append({"source": source, "refresh_id": int(match.group(2)),
                                   **counts, **committed, "quality_flags": active_flags,
                                   "committed_metrics_available": bool(committed),
                                   "strategy_attempt_count": sum(attempts.values()),
                                   "parser_error_count": sum(errors.values())})
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    invalid += 1
    status = "no_log" if not log_path.is_file() else "no_events" if observed == 0 else "observed"
    report = {"status": status, "events_observed": observed,
              "events_exported": len(events), "events_invalid": invalid,
              "events_omitted": max(0, observed - invalid - len(events)),
              "absence_reconciliation_permitted": False, "events": events,
              "quality_flag_counts": {flag: sum(flag in event["quality_flags"] for event in events)
                                      for flag in QUALITY_FLAGS}}
    # Events have a strict cap and contain only aggregate integers + bounded names.
    rendered = json.dumps(report, sort_keys=True, separators=(",", ":"))
    if len(rendered.encode("utf-8")) > MAX_BYTES:
        # Do not truncate JSON. Drop events until the document fits.
        while report["events"] and len(rendered.encode("utf-8")) > MAX_BYTES:
            removed = report["events"].pop()
            for flag in QUALITY_FLAGS:
                report["quality_flag_counts"][flag] -= int(flag in removed["quality_flags"])
            report["events_exported"] -= 1
            report["events_omitted"] += 1
            rendered = json.dumps(report, sort_keys=True, separators=(",", ":"))
    output_path.write_text(rendered + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/carscanner-refresh.log")
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("extraction-diagnostics.json")
    result = extract_summary(source, target)
    print({k: v for k, v in result.items() if k != "events"})
