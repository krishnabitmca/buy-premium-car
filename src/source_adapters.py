from __future__ import annotations

"""Source-isolated marketplace adapter execution.

The adapter layer is deliberately the only execution boundary between the
source registry and marketplace HTTP/parsing. A failure in one adapter must
never fail the customer search or refresh work for another source.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol
import time

from .live_marketplaces import (
    _execute_source,
    _targeted_source_urls,
    fetch_text,
    parse_live_listings,
    parse_visible_listing_links,
    _identity_matches_query,
)
from .source_intelligence import normalize_condition


@dataclass(frozen=True)
class AdapterRequest:
    query: str = ""
    condition: str = "both"
    budget_min: float | None = None
    budget_max: float | None = None
    destination: str | None = None


@dataclass
class AdapterResult:
    source_name: str
    listings: list[dict[str, Any]] = field(default_factory=list)
    status: str = "unavailable"
    latency_ms: int = 0
    error: str | None = None
    query_url: str | None = None


class SourceAdapter(Protocol):
    source_name: str

    def fetch(self, request: AdapterRequest) -> AdapterResult:
        ...


class BuiltinMarketplaceAdapter:
    """Adapter for a verified registry source using the existing parser.

    The adapter receives exactly one source registry record and can only fetch
    the URL selected for that source. It does not fan out to other sources.
    """

    def __init__(self, source: dict[str, Any]):
        self.source = source
        self.source_name = str(source.get("name") or "")

    def _url(self, request: AdapterRequest) -> str:
        targeted = _targeted_source_urls(request.query)
        return targeted.get(self.source_name, str(self.source.get("url") or ""))

    def fetch(self, request: AdapterRequest) -> AdapterResult:
        started = time.monotonic()
        url = self._url(request)
        if not url:
            return AdapterResult(
                source_name=self.source_name,
                status="unavailable",
                error="adapter has no source URL",
            )

        try:
            html = fetch_text(url)
            parsed = parse_live_listings(html, self.source_name, url)
            if not parsed and request.query:
                parsed = parse_visible_listing_links(
                    html, self.source_name, url, request.query
                )

            wanted_condition = normalize_condition(request.condition)
            filtered: list[dict[str, Any]] = []
            for row in parsed:
                if request.query and not _identity_matches_query(row, request.query):
                    continue
                actual = normalize_condition(row.get("condition_signal"))
                if wanted_condition in {"used", "demo"} and actual != wanted_condition:
                    continue
                if request.budget_min is not None and (
                    row.get("price_lakh") is None
                    or float(row["price_lakh"]) < request.budget_min
                ):
                    continue
                if request.budget_max is not None and (
                    row.get("price_lakh") is None
                    or float(row["price_lakh"]) > request.budget_max
                ):
                    continue
                row["identity_confidence"] = (
                    1.0 if row.get("brand") and row.get("model") else 0.0
                )
                row["identity_evidence"] = [
                    "brand", "model", "listing_name", "url"
                ]
                filtered.append(row)

            return AdapterResult(
                source_name=self.source_name,
                listings=filtered,
                status="live",
                latency_ms=int((time.monotonic() - started) * 1000),
                query_url=url,
            )
        except Exception as exc:
            return AdapterResult(
                source_name=self.source_name,
                status="unavailable",
                latency_ms=int((time.monotonic() - started) * 1000),
                error=str(exc)[:300],
                query_url=url,
            )


def build_verified_adapters(
    registry: list[dict[str, Any]],
) -> list[BuiltinMarketplaceAdapter]:
    """Build adapters only for sources explicitly marked live.

    Candidate/draft/degraded/disabled sources are never executed here.
    Degraded sources are intentionally excluded until the control plane
    promotes them back to live.
    """
    return [
        BuiltinMarketplaceAdapter(source)
        for source in registry
        if source.get("adapter_status") == "live"
    ]


def execute_adapters(
    request: AdapterRequest,
    registry: list[dict[str, Any]],
    *,
    max_workers: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Execute verified adapters independently and aggregate their results.

    A source exception is converted into that source's status record. Other
    adapters continue and the aggregate search remains successful.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    adapters = build_verified_adapters(registry)
    if not adapters:
        return [], []

    def run(adapter: BuiltinMarketplaceAdapter) -> AdapterResult:
        return adapter.fetch(request)

    results: list[AdapterResult] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(adapters))) as pool:
        future_to_adapter = {
            pool.submit(run, adapter): adapter for adapter in adapters
        }
        for future in as_completed(future_to_adapter):
            adapter = future_to_adapter[future]
            try:
                results.append(future.result())
            except Exception as exc:
                # Defensive isolation even if an adapter implementation itself
                # violates the fetch contract. Preserve the source identity.
                results.append(
                    AdapterResult(
                        source_name=adapter.source_name,
                        status="unavailable",
                        error=str(exc)[:300],
                    )
                )

    results.sort(key=lambda x: x.source_name)
    vehicles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    source_by_name = {str(s.get("name")): s for s in registry}

    for result in results:
        source = source_by_name.get(result.source_name, {})
        vehicles.extend(result.listings)
        status = {
            "source": result.source_name,
            "status": result.status,
            "listings_found": len(result.listings),
            "query_url": result.query_url,
            "source_type": source.get("source_type"),
            "query_strategy": source.get("query_strategy"),
            "latency_ms": result.latency_ms,
        }
        if result.error:
            status["error"] = result.error
        statuses.append(status)

    return vehicles, statuses
