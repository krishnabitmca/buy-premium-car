"""Continuously schedule and consume persistent inventory refresh work.

Run separately from customer HTTP requests. Multiple instances safely compete
for PostgreSQL SKIP LOCKED claims; each instance fetches one source at a time.
"""
from __future__ import annotations

import argparse
import logging
import time

from .inventory_refresh_planner import schedule_refreshes
from .inventory_refresh_worker import run_batch
from .source_registry_db import require_database

log = logging.getLogger(__name__)


def run_cycle(limit: int) -> dict[str, int]:
    scheduled = schedule_refreshes(limit=limit)
    return {"scheduled": scheduled, **run_batch(limit)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.interval_seconds < 10:
        parser.error("interval must be at least 10 seconds")
    require_database()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            result = run_cycle(args.limit)
            log.info("Inventory cycle: %s", result)
            if args.once:
                raise SystemExit(1 if result["failed"] else 0)
        except Exception:
            log.exception("Inventory cycle failed; persistent jobs remain recoverable")
            if args.once:
                raise
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
