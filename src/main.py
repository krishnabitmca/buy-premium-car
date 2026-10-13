"""Daily production acquisition using the canonical PostgreSQL pipeline.

Legacy SQLite/browser reports are available explicitly via
``python -m src.legacy_reports`` and never feed production watches.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .inventory_db import iter_inventory
from .inventory_service import run_cycle
from .source_registry_db import require_database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--export-json", help="Optional Postgres-derived diagnostic export")
    args = parser.parse_args()
    require_database()
    result = run_cycle(args.limit)
    if args.export_json:
        path = Path(args.export_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Stream records to avoid loading national inventory into memory.
        with path.open("w", encoding="utf-8") as handle:
            handle.write('{"mode":"postgres_export","generated_at":')
            handle.write(json.dumps(datetime.now(timezone.utc).isoformat()))
            handle.write(',"vehicles":[')
            first = True
            for rows in iter_inventory():
                for row in rows:
                    if not first:
                        handle.write(",")
                    handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False))
                    first = False
            handle.write("]}")
    print(result)
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
