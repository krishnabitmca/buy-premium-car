from __future__ import annotations

"""Query-driven open-web source expansion for customer car searches.

The registry is a cache/control plane, never the search universe. For a concrete
brand/model intent this module discovers relevant web inventory sources, validates
that the pages expose matching inventory, and returns ephemeral sources that can
be searched immediately. Persistence/promotion remains an optimization.
"""

from urllib.parse import urlparse
from typing import Any
import hashlib

from .config import load_settings
from .discovery import discover
from .live_marketplaces import fetch_text, parse_live_listings, parse_visible_listing_links, parse_generic_detail_page
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
    diagnostics: dict[str, Any] | None = None,
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
    # Request-time discovery is intentionally bounded. Continuous/background
    # indexing does the deep sweep; this path fills an immediate coverage gap.
    settings.search={**settings.search,"engines":["duckduckgo,startpage,mojeek,yahoo"],"max_discovery_results_per_query":10}
    candidates=discover(
        settings, known_domains, demand=demand,
        include_known_domain_urls=True, max_queries=9 if normalize_condition(condition)=="demo" else 4,
    )
    if diagnostics is not None:
        diagnostics["candidates_found"]=len(candidates)
        diagnostics["candidate_sample"]=[str(c.url) for c in candidates[:10]]
        diagnostics["pages_fetched"]=0
        diagnostics["identity_matches"]=0
        diagnostics["condition_matches"]=0

    expanded=[]
    validated_urls=set()
    for candidate in candidates:
        if len(expanded)>=max_sources:
            break
        try:
            html=fetch_text(candidate.url)
            if diagnostics is not None:
                diagnostics["pages_fetched"]+=1
            rows=parse_live_listings(html, f"Web - {candidate.domain}", candidate.url)
            if not rows:
                rows=parse_visible_listing_links(
                    html, f"Web - {candidate.domain}", candidate.url, f"{brand} {model}"
                )
            identity_rows=[row for row in rows if _identity(row,brand,model)]
            if diagnostics is not None:
                diagnostics["identity_matches"]+=len(identity_rows)
            wanted=normalize_condition(condition)
            matching=list(identity_rows)
            validated_endpoint=candidate.url
            if wanted=="demo":
                matching=[row for row in identity_rows if str(row.get("condition_signal") or "").lower() in {"demo","demonstrator"}]
                # Catalogue cards often omit condition. Confirm a bounded number
                # of detail pages rather than trusting a /demo route or source name.
                if not matching:
                    for row in identity_rows[:3]:
                        detail_url=str(row.get("url") or "")
                        if not detail_url or detail_url.rstrip("/")==str(candidate.url).rstrip("/"):
                            continue
                        try:
                            detail_html=fetch_text(detail_url)
                            if diagnostics is not None:
                                diagnostics["pages_fetched"]+=1
                            detail_rows=parse_live_listings(detail_html, f"Web - {candidate.domain}", detail_url)
                            if not detail_rows:
                                detail_rows=parse_generic_detail_page(
                                    detail_html, f"Web - {candidate.domain}", detail_url, f"{brand} {model}"
                                )
                            confirmed=[
                                r for r in detail_rows
                                if _identity(r,brand,model)
                                and str(r.get("condition_signal") or "").lower() in {"demo","demonstrator"}
                            ]
                            if confirmed:
                                matching=confirmed
                                validated_endpoint=detail_url
                                break
                        except Exception:
                            continue
            elif wanted=="used":
                matching=[row for row in identity_rows if str(row.get("condition_signal") or "").lower() not in {"demo","demonstrator"}]
            if diagnostics is not None:
                diagnostics["condition_matches"]+=len(matching)
            if not matching:
                continue
        except Exception:
            continue

        normalized_url=str(validated_endpoint or "").rstrip("/")
        if normalized_url in validated_urls:
            continue
        validated_urls.add(normalized_url)
        expanded.append({
            "name":f"Web - {candidate.domain} - {hashlib.sha1(normalized_url.encode()).hexdigest()[:8]}",
            "url":validated_endpoint,
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
    """Merge cached registry with newly discovered inventory endpoints.

    URL, not domain, is the identity here: a known marketplace/dealer can expose
    a previously unknown brand/model inventory route that must be searchable.
    """
    merged=list(registry)
    seen_urls={str(s.get("url") or "").rstrip("/") for s in registry if s.get("url")}
    for source in discovered:
        url=str(source.get("url") or "").rstrip("/")
        if url and url not in seen_urls:
            merged.append(source)
            seen_urls.add(url)
    return merged
