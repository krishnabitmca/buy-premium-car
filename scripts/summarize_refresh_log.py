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
                    events.append({"source": source, "refresh_id": int(match.group(2)),
                                   **counts, "strategy_attempt_count": sum(attempts.values()),
                                   "parser_error_count": sum(errors.values())})
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    invalid += 1
    status = "no_log" if not log_path.is_file() else "no_events" if observed == 0 else "observed"
    report = {"status": status, "events_observed": observed,
              "events_exported": len(events), "events_invalid": invalid,
              "events_omitted": max(0, observed - invalid - len(events)),
              "absence_reconciliation_permitted": False, "events": events}
    # Events have a strict cap and contain only aggregate integers + bounded names.
    rendered = json.dumps(report, sort_keys=True, separators=(",", ":"))
    if len(rendered.encode("utf-8")) > MAX_BYTES:
        # Do not truncate JSON. Drop events until the document fits.
        while report["events"] and len(rendered.encode("utf-8")) > MAX_BYTES:
            report["events"].pop()
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
