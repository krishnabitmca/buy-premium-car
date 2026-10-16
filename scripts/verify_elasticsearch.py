"""Read-only parity and timing check against configured inventory providers."""
import json
import os
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_local import load_env
from src import elastic_inventory as elastic, inventory_db


def main():
    load_env()
    os.environ['CARSCANNER_SEARCH_ENGINE'] = 'elasticsearch'
    report = []
    for brand in ('BMW', 'Mercedes-Benz', 'Audi', 'Toyota', 'Porsche', 'Jaguar'):
        for extra in ({}, {'budget_min': 30, 'budget_max': 50}, {'condition': 'demo'}, {'offset': 50}):
            args = dict(query=brand, limit=50, return_count=True, **extra)
            start = time.perf_counter()
            expected = inventory_db.search_inventory(**args)
            pg_ms = (time.perf_counter() - start) * 1000
            elastic._retry_after = 0
            start = time.perf_counter()
            actual = elastic.search_inventory(**args)
            es_ms = (time.perf_counter() - start) * 1000
            # Tie ordering may vary only where identical asking prices coincide.
            expected_prices = [r['price_lakh'] for r in expected[0]]
            actual_prices = [r['price_lakh'] for r in actual[0]]
            passed = (elastic.backend() == 'elasticsearch' and actual[2] == expected[2]
                      and expected_prices == actual_prices)
            report.append(dict(filters=args, ok=passed, engine=elastic.backend(),
                               postgres_count=expected[2], elastic_count=actual[2],
                               postgres_ms=round(pg_ms, 2), elastic_ms=round(es_ms, 2)))
    print(json.dumps(report, indent=2))
    if not all(r['ok'] for r in report):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
