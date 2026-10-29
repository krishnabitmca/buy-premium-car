"""Opt-in, bounded Apify OLX proof of concept. Never writes to canonical inventory.

Usage (only after confirming source permissions):
  APIFY_OLX_POC_ENABLED=1 APIFY_TOKEN=... python scripts/apify_olx_poc.py --query "BMW X1" --limit 10

Prints aggregate metrics only; never logs tokens, seller data or raw listings.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

ACTOR = "fetch_cat~olx-india-listings-scraper"
API = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"
MAX_ITEMS = 25

def summarize(rows):
    valid = []
    images = 0
    seen = set()
    duplicates = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = row.get("url") or row.get("listingUrl") or row.get("adUrl")
        title = row.get("title")
        price = row.get("price")
        if not isinstance(url, str) or urlparse(url).hostname not in ("olx.in", "www.olx.in"):
            continue
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
            continue
        if url in seen:
            duplicates += 1
            continue
        seen.add(url)
        valid.append(row)
        if row.get("images") or row.get("imageUrl") or row.get("image"):
            images += 1
    return {"returned": len(rows), "valid_priced": len(valid), "duplicates": duplicates,
            "with_images": images, "rejected": len(rows)-len(valid)-duplicates}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="BMW X1")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if os.getenv("APIFY_OLX_POC_ENABLED") != "1":
        sys.exit("POC disabled; set APIFY_OLX_POC_ENABLED=1 only after source-use review")
    token = os.getenv("APIFY_TOKEN")
    if not token:
        sys.exit("Missing APIFY_TOKEN secret")
    if not 1 <= args.limit <= MAX_ITEMS:
        sys.exit("limit must be between 1 and 25")
    if not args.query.strip() or len(args.query) > 80:
        sys.exit("query must contain 1-80 characters")
    payload = json.dumps({"queries": [args.query], "maxItems": args.limit,
                          "includeDetails": False, "maxRuntimeSecs": 90}).encode()
    request = urllib.request.Request(API, data=payload,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=110) as response:
            rows = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError):
        sys.exit("Apify request failed; check run details privately in Apify Console")
    if not isinstance(rows, list):
        sys.exit("Unexpected dataset response")
    print(json.dumps({"actor": ACTOR, "query": args.query, **summarize(rows)}))

if __name__ == "__main__":
    main()
