"""Continuously schedule and consume persistent inventory refresh work.

Run separately from customer HTTP requests. Multiple instances safely compete
for PostgreSQL SKIP LOCKED claims; each instance fetches one source at a time.
"""
from __future__ import annotations

import argparse
import logging
import time
from collections import Counter

from .inventory_refresh_planner import schedule_refreshes
from .inventory_refresh_worker import run_batch
from .source_registry_db import require_database
from .inventory_lifecycle import run_cycle as renew_listings

log = logging.getLogger(__name__)


def acquisition_plan(limit):
    """Reserve every work class before expanding any discovery bucket."""
    slots=('general','demo','catalogues','models','continuations','catalogues','catalogues','models','continuations','catalogues')
    counts=Counter(slots[i%len(slots)] for i in range(max(1,min(int(limit),100))))
    return [(kind,counts[kind],{} if kind=='general' else {kind+'_only':True})
            for kind in dict.fromkeys(slots) if counts[kind]]


def run_cycle(limit: int) -> dict[str, int]:
    try:
        scheduled = schedule_refreshes(limit=limit)
        acquisition={'completed':0,'failed':0}
        consumed=0
        failure=None
        for kind,budget,kwargs in acquisition_plan(limit):
            try:
                for key,count in run_batch(budget,**kwargs).items():
                    acquisition[key]=acquisition.get(key,0)+count
                    consumed+=count
            except Exception as exc:
                failure=failure or exc
                log.error('Acquisition bucket failed: %s',kind)
        # Reserved buckets are priorities, not hard caps on throughput. When a
        # specialized bucket runs dry, let generic eligible jobs use its slots.
        # Do not retry a failed bucket in the same cycle.
        if not failure and consumed < limit:
            for key,count in run_batch(limit-consumed).items():
                acquisition[key]=acquisition.get(key,0)+count
        if failure:raise failure
    finally:
        renewal=renew_listings(limit)
    return {"scheduled": scheduled, **acquisition,'lifecycle':renewal}


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
