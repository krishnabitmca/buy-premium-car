from __future__ import annotations

"""Discover, validate, and promote new CarScanner source websites.

This job is intentionally separate from customer search. Search only consumes
sources that have passed a real inventory validation, so search quality does
not depend on unverified search-engine discoveries.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import time
from urllib.parse import urlparse

from src.config import load_settings
from src.source_monitoring import registered_candidates, plan_probes
from src.discovery import discover
from src.live_marketplaces import fetch_text, parse_live_listings, parse_visible_listing_links, parse_generic_detail_page
from src.source_intelligence import load_source_registry, normalize_condition
from src.source_registry_db import (
    enabled as source_db_enabled,
    promote_discovery,
    record_discoveries,
    load_search_demand,
    load_probe_history, claim_source_probe, finish_source_probe,
)


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _matches_candidate(row: dict, candidate: object) -> bool:
    brand_hint = str(getattr(candidate, "brand_hint", None) or "").strip().lower()
    condition_hint = normalize_condition(getattr(candidate, "condition", "both"))

    if brand_hint and str(row.get("brand") or "").strip().lower() != brand_hint:
        return False

    actual = normalize_condition(row.get("condition_signal"))
    if condition_hint in {"used", "demo"} and actual != condition_hint:
        return False
    return True


def validate_candidate(candidate: object) -> tuple[int, str | None]:
    url = str(getattr(candidate, "url", "") or "").strip()
    if not url:
        return 0, "missing url"

    source_name = f"Discovery validation - {_domain(url)}"
    started = time.monotonic()
    try:
        html = fetch_text(url)
        rows = parse_live_listings(html, source_name, url)
        if not rows:
            rows = parse_visible_listing_links(
                html,
                source_name,
                url,
                str(getattr(candidate, "brand_hint", "") or ""),
            )

        matching = [row for row in rows if _matches_candidate(row, candidate)]
        # Demo catalogue cards frequently omit condition. Follow a bounded set
        # of vehicle detail links and require explicit detail-page demo evidence.
        if not matching and normalize_condition(getattr(candidate, "condition", "both")) == "demo":
            for row in rows[:8]:
                detail_url = str(row.get("url") or "").strip()
                if not detail_url or detail_url.rstrip("/") == url.rstrip("/"):
                    continue
                try:
                    detail_html = fetch_text(detail_url)
                    detail_rows = parse_live_listings(detail_html, source_name, detail_url)
                    if not detail_rows:
                        detail_rows = parse_generic_detail_page(
                            detail_html, source_name, detail_url,
                            str(getattr(candidate, "brand_hint", "") or ""),
                        )
                    matching.extend(r for r in detail_rows if _matches_candidate(r, candidate))
                except Exception:
                    continue
        latency_ms = int((time.monotonic() - started) * 1000)
        if len(matching) < 2:
            return len(matching), f"inventory validation found {len(matching)} matching listings in {latency_ms}ms; two required for staging"
        return len(matching), None
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {str(exc)[:160]}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--min-confidence", type=float, default=0.70)
    parser.add_argument('--skip-web-discovery', action='store_true', help='Probe registered candidates only')
    parser.add_argument('--plan-only', action='store_true', help='Read-only candidate plan; no fetch or database writes')
    parser.add_argument('--report', default='coverage/source-expansion.json')
    parser.add_argument('--max-discovery-queries', type=int, choices=range(1,25), default=6)
    args = parser.parse_args()

    if not source_db_enabled():
        raise SystemExit(
            "SOURCE_INTELLIGENCE_DATABASE_URL/DATABASE_URL is required for source promotion"
        )

    settings = load_settings(args.config)
    registry = load_source_registry(from_database=True)
    known_domains = {
        _domain(str(source.get("url") or ""))
        for source in registry
        if source.get("url")
    }

    demand = load_search_demand(limit=100, lookback_hours=168)
    # Rotate across the full query bank instead of repeating its first brands.
    # This is a target time window, not evidence that missed dispatches ran.
    query_offset = int(time.time() // (3*3600)) * args.max_discovery_queries
    found = [] if args.skip_web_discovery or args.plan_only else discover(settings, known_domains, demand=demand,
        include_known_domain_urls=True,max_queries=args.max_discovery_queries,query_offset=query_offset)
    print(f"demand_intents={len(demand)}")
    # Known candidates must be probed even if search engines do not return
    # them. Merge versioned seeds with the DB registry; existing live URLs are
    # skipped and validation still stages adapters rather than enabling them.
    seeds = registered_candidates([*registry, *load_source_registry(from_database=False)])
    history = load_probe_history([item.url for item in [*seeds, *found]])
    candidates = plan_probes(seeds, found, history, args.min_confidence, args.max_candidates)
    print(f"registered_candidates={len(seeds)}")

    report = dict(started_at=datetime.now(timezone.utc).isoformat(),plan_only=args.plan_only,
        registered_candidates=len(seeds),web_candidates=len(found),
        selected_urls=[item.url for item in candidates],results=[],
        max_discovery_queries=args.max_discovery_queries,query_offset=query_offset,
        policy='Least recently attempted within registered/web pools; one in five slots reserved for web, idle slots borrowed. Staged sources await review.')
    def save_report():
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    save_report()
    if args.plan_only:
        print(f'planned={len(candidates)}; no probes or writes performed')
        return

    discoveries = [
        {
            "domain": item.domain,
            "url": item.url,
            "title": item.title,
            "snippet": item.snippet,
            "query": item.query,
            "source_type": item.source_type,
            "condition": item.condition,
            "segment": item.segment,
            "brand_hint": item.brand_hint or "",
            "candidate_confidence": item.candidate_confidence,
        }
        for item in candidates
    ]
    recorded = record_discoveries(discoveries)

    promoted = []
    rejected = 0
    for item in candidates:
        token = claim_source_probe(item)
        if not token:
            report['results'].append(dict(url=item.url,status='deferred'))
            save_report()
            continue
        listings_found, error = validate_candidate(item)
        result = dict(url=item.url,domain=item.domain,listings_found=listings_found,
            status='validated' if listings_found>=2 else 'rejected',error=error,
            checked_at=datetime.now(timezone.utc).isoformat())
        if not finish_source_probe(item, token, result):
            result['status'] = 'superseded'
            report['results'].append(result)
            save_report()
            continue
        report['results'].append(result)
        save_report()
        if listings_found < 2:
            rejected += 1
            print(f"REJECT domain={item.domain} reason={error}")
            continue

        name = promote_discovery(
            {
                "domain": item.domain,
                "url": item.url,
                "title": item.title,
                "query": item.query,
                "source_type": item.source_type,
                "condition": item.condition,
                "segment": item.segment,
                "brand_hint": item.brand_hint or "",
                "candidate_confidence": item.candidate_confidence,
            },
            listings_found=listings_found,
        )
        if name:
            promoted.append((name, listings_found))
            result['status'] = 'staged'
            save_report()
            print(
                f"STAGED source={name} listings={listings_found} "
                f"brand={item.brand_hint or 'all'} condition={item.condition}"
            )

    report['completed_at'] = datetime.now(timezone.utc).isoformat()
    save_report()
    print(
        f"discovered={len(found)} candidates={len(candidates)} "
        f"recorded={recorded} staged={len(promoted)} rejected={rejected}"
    )


if __name__ == "__main__":
    main()
