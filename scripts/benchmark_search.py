"""Reproducible API timings, including misses and optional concurrent reads.

Example: python scripts/benchmark_search.py --samples 24 --concurrency 4
This measures the configured test server; it does not certify national capacity.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import statistics
import time
import urllib.request


def request(endpoint, query):
    started = time.perf_counter()
    payload = json.dumps({'query': query, 'condition': 'both', 'page_size': 50}).encode()
    req = urllib.request.Request(endpoint, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        body = json.load(response)
        timings = {}
        for part in response.headers.get('Server-Timing', '').split(','):
            name, _, duration = part.strip().partition(';dur=')
            if duration: timings[name] = float(duration)
        if not body.get('ok'): raise RuntimeError('Search returned a non-success payload')
    return {'query': query, 'milliseconds': round((time.perf_counter()-started)*1000, 2),
            'mode': body.get('mode'), 'observations': body.get('inventory_total'),
            'results': len(body.get('results') or []), 'stages_ms': timings}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', default='http://127.0.0.1:8000/api/search')
    parser.add_argument('--samples', type=int, default=24)
    parser.add_argument('--concurrency', type=int, default=1)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000 or not 1 <= args.concurrency <= 32:
        parser.error('Samples must be 1–1000; concurrency must be 1–32')
    queries = ['BMW', 'Audi', 'Toyota', 'Honda', 'Mercedes-Benz', 'Tata']
    first = request(args.endpoint, queries[0])
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        rows = list(pool.map(lambda index: request(args.endpoint, queries[index % len(queries)]), range(args.samples)))
    elapsed = time.perf_counter()-started
    ordered = sorted(row['milliseconds'] for row in rows)
    def percentile(p): return ordered[max(0, math.ceil(len(ordered)*p)-1)]
    report = {'concurrency': args.concurrency, 'samples': len(rows), 'first_request': first,
              'median_ms': statistics.median(ordered), 'p95_ms': percentile(.95),
              'p99_ms': percentile(.99), 'throughput_requests_per_second': round(len(rows)/elapsed, 2),
              'note': 'Closed-loop sample against one configured server; not a national-load certification.',
              'results': rows}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key not in {'results','first_request'}}))


if __name__ == '__main__': main()
