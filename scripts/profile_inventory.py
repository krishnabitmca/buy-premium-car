"""Profile the exact inventory SELECT; never expose this through customer input."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_local import load_env
from src.inventory_db import search_inventory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    load_env()
    plans = []
    for query in ['BMW', 'Audi', '']:
        plan = search_inventory(query=query, return_count=True, limit=50,
                                require_persistence=True, explain=True)
        plans.append({'query': query, 'plan': plan})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plans, indent=2), encoding='utf-8')
    print(json.dumps([{'query': row['query'], 'planning_ms': row['plan'][0]['Planning Time'],
                      'execution_ms': row['plan'][0]['Execution Time']} for row in plans]))


if __name__ == '__main__': main()
