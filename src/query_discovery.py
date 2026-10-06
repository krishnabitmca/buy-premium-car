from __future__ import annotations

"""Query-driven open-web source expansion for customer car searches.

The registry is a cache/control plane, never the search universe. For a concrete
brand/model intent this module discovers relevant web inventory sources, validates
that the pages expose matching inventory, and returns ephemeral sources that can
be searched immediately. Persistence/promotion remains an optimization.
"""

from dataclasses import asdict
from urllib.parse import urlparse
from typing import Any

from .config import load_settings
from .discovery import discover
from .live_marketplaces import fetch_text, parse_live_listings, parse_visible_listing_links
from .source_intelligence import normalize_condition


def _domain(url: str) -> str:
    return urlparse(str(url or "")).netloc.lower().removeprefix("www.")


def _identity(row: dict[str, Any], brand: str, model: str) -> bool:
    hay=" ".join(str(row.get(k) or "") for k in ("brand","model","listing_name","variant","url")).lower()
    return str(brand or "").lower() in hay and str(model or "").lower() in hay


def discover_for_intent(
    *,
    brand: str,
    model: str,
    condition: str,
    known_registry: list[dict[str, Any]],
    max_sources: int = 12,
) -> list[dict[str, Any]]:
    """Discover and validate sources for this exact customer intent.

    Condition influences web discovery terms, but never source eligibility.
    Individual listing condition is filtered later by the adapter.
    """
    brand=str(brand or "").strip()
    model=str(model or "").strip()
    if not brand or not model:
        return []

    settings=load_settings("config/settings.yaml")
    # Keep discovery focused on the exact customer intent instead of sweeping the
    # entire configured brand universe on the request path.
    settings.search={**settings.search,"brands":[],"city_hints_per_run":0}
    demand=[{"brand":brand,"model":model,"condition":normalize_condition(condition),"destination_state":""}]
    known_domains={_domain(s.get("url")) for s in known_registry if s.get("url")}
    candidates=discover(settings, known_domains, demand=demand)

    expanded=[]
    for candidate in candidates:
        if len(expanded)>=max_sources:
            break
        try:
            html=fetch_text(candidate.url)
            rows=parse_live_listings(html, f"Web - {candidate.domain}", candidate.url)
            if not rows:
                rows=parse_visible_listing_links(
                    html, f"Web - {candidate.domain}", candidate.url, f"{brand} {model}"
                )
            matching=[row for row in rows if _identity(row,brand,model)]
            if not matching:
                continue
        except Exception:
            continue

        expanded.append({
            "name":f"Web - {candidate.domain}",
            "url":candidate.url,
            "source_type":candidate.source_type,
            "adapter_status":"live",
            "geography":"india",
            "query_strategy":"open_web_intent",
            "priority":70,
            "enabled":True,
            "brands":[brand],
            # Source-level condition is deliberately broad. Listing-level evidence
            # determines used/demo after extraction.
            "conditions":["used","demo"],
            "segments":[candidate.segment],
            "metadata":{
                "ephemeral_discovery":True,
                "discovery_query":candidate.query,
                "candidate_confidence":candidate.candidate_confidence,
                "validated_matching_rows":len(matching),
            },
        })
    return expanded


def merge_source_universe(
    registry: list[dict[str, Any]],
    discovered: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge cached registry and current-web discoveries by domain."""
    merged=list(registry)
    seen={_domain(s.get("url")) for s in registry if s.get("url")}
    for source in discovered:
        domain=_domain(source.get("url"))
        if domain and domain not in seen:
            merged.append(source)
            seen.add(domain)
    return merged
