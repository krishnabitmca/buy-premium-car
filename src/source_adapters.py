from __future__ import annotations

"""Source-isolated marketplace adapter execution."""

from dataclasses import dataclass, field
from typing import Any, Protocol
import time

from . import live_marketplaces as live_marketplaces
from .source_intelligence import normalize_condition
from .source_registry_db import enabled as registry_db_enabled, _connect as registry_connect


# Compatibility seams: keep HTTP/parsing dynamically delegated so existing
# tests/integrations can patch this adapter boundary without patching the
# underlying marketplace module.
def fetch_text(url: str) -> str:
    return live_marketplaces.fetch_text(url)


def parse_live_listings(html: str, source_name: str, url: str) -> list[dict[str, Any]]:
    return live_marketplaces.parse_live_listings(html, source_name, url)


def parse_visible_listing_links(
    html: str, source_name: str, url: str, query: str
) -> list[dict[str, Any]]:
    return live_marketplaces.parse_visible_listing_links(html, source_name, url, query)


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
    """Adapter for a verified registry source using the existing parser."""

    def __init__(self, source: dict[str, Any]):
        self.source = source
        self.source_name = str(source.get("name") or "")

    def _urls(self, request: AdapterRequest) -> list[str]:
        targeted = live_marketplaces._targeted_source_urls(
            request.query, request.condition, registry=[self.source]
        )
        urls=[]
        primary=targeted.get(self.source_name) or str(self.source.get("url") or "")
        if primary:
            urls.append(primary)
        # Validated discovered endpoints are first-class inventory surfaces.
        # Domain identity must never collapse dealer/catalogue/demo endpoints.
        for endpoint in self.source.get("endpoints") or []:
            if endpoint.get("condition") and normalize_condition(request.condition) not in {"both", normalize_condition(endpoint["condition"])}:
                continue
            if endpoint.get("is_active", True) is False:
                continue
            url=str(endpoint.get("url") or "").strip()
            if url and url not in urls:
                urls.append(url)
        return urls[:12]

    def fetch(self, request: AdapterRequest) -> AdapterResult:
        started = time.monotonic()
        urls = self._urls(request)
        url = urls[0] if urls else ""
        if not adapter_execution_allowed(self.source_name):
            return AdapterResult(
                source_name=self.source_name,
                status="circuit_open",
                error="adapter circuit is open",
            )

        if not url:
            return AdapterResult(
                source_name=self.source_name,
                status="unavailable",
                error="adapter has no source URL",
            )

        try:
            all_parsed=[]
            fetched_urls=[]
            parser_strategy = str(self.source.get("parser_strategy") or (self.source.get("metadata") or {}).get("parser_strategy") or "").strip().lower()
            partial_error = None
            for endpoint_url in urls:
                if parser_strategy == "sundaram_cards":
                    from .demo_dealers import fetch_sundaram
                    rows, partial_error = fetch_sundaram(endpoint_url, self.source_name, fetch_text)
                    all_parsed.extend(rows)
                    fetched_urls.append(endpoint_url)
                    continue
                if parser_strategy == "gurudev_stock":
                    from .demo_dealers import parse_gurudev
                    all_parsed.extend(parse_gurudev(fetch_text(endpoint_url), self.source_name, endpoint_url))
                    fetched_urls.append(endpoint_url)
                    continue
                if parser_strategy == "mercedes_inventory":
                    from .oem_inventory import fetch_mercedes_inventory
                    all_parsed.extend(fetch_mercedes_inventory(
                        endpoint_url, request.query, normalize_condition(request.condition), self.source_name
                    ))
                    fetched_urls.append(endpoint_url)
                    continue
                try:
                    html = fetch_text(endpoint_url)
                except Exception as exc:
                    if len(urls) == 1:
                        raise
                    partial_error = (partial_error or "") + f"{endpoint_url}: {type(exc).__name__}; "
                    continue
                fetched_urls.append(endpoint_url)
                if parser_strategy == "motozite_cards":
                    parsed = live_marketplaces.parse_motozite_cards(
                        html, self.source_name, endpoint_url, request.query, condition="both"
                    )
                elif parser_strategy in {"bbt_cards", "autobest_cards", "luxuryride_cards", "ninthgear_cards"}:
                    from .dealer_inventory import parse_dealer_cards
                    parsed = parse_dealer_cards(html, self.source_name, endpoint_url, parser_strategy, request.query)
                elif parser_strategy == "bmw_cards":
                    parsed = live_marketplaces.parse_bmw_listing_cards(
                        html, self.source_name, endpoint_url, request.query
                    )
                elif parser_strategy in {"embedded_json", "spinny_embedded"}:
                    parsed = live_marketplaces.parse_embedded_marketplace_listings(
                        html, self.source_name, endpoint_url, request.query
                    )
                else:
                    parsed = parse_live_listings(html, self.source_name, endpoint_url)
                if not parsed:
                    parsed = parse_visible_listing_links(
                        html, self.source_name, endpoint_url, request.query
                    )
                if not parsed and request.query:
                    parsed = live_marketplaces.parse_generic_detail_page(
                        html, self.source_name, endpoint_url, request.query
                    )
                all_parsed.extend(parsed)
            if not fetched_urls:
                raise RuntimeError(partial_error or "No inventory endpoint responded")
            # The same car may be exposed by canonical, dealer and campaign
            # endpoints. Deduplicate by listing URL before condition filtering.
            parsed=[]
            seen_listing_urls=set()
            for row in all_parsed:
                listing_url=str(row.get("url") or "").strip()
                provenance=row.get("provenance") or {}
                source_url=str(provenance.get("source_url") or "").strip()
                # A catalogue/card without its own href legitimately shares the
                # endpoint URL with sibling vehicles. In that case URL is not a
                # vehicle identity and must not collapse distinct inventory.
                if listing_url and (
                    not source_url
                    or listing_url.rstrip("/") != source_url.rstrip("/")
                ):
                    key=("url", listing_url.rstrip("/"))
                else:
                    key=(
                        "vehicle",
                        str(row.get("brand") or "").strip().lower(),
                        str(row.get("model") or "").strip().lower(),
                        str(row.get("listing_name") or "").strip().lower(),
                        row.get("price_lakh"),
                        row.get("mfg_year"),
                        row.get("km"),
                    )
                if key in seen_listing_urls:
                    continue
                seen_listing_urls.add(key)
                parsed.append(row)

            wanted_condition = normalize_condition(request.condition)
            filtered: list[dict[str, Any]] = []
            for row in parsed:
                if request.query and not live_marketplaces._identity_matches_query(row, request.query):
                    continue
                actual = normalize_condition(row.get("condition_signal"))
                # Demonstrator searches are fail-closed: only explicit per-listing
                # demonstrator evidence may enter the response. Used searches may
                # retain unknown rows from ordinary used inventory pages.
                if wanted_condition == "demo" and actual != "demo":
                    continue
                if wanted_condition == "used" and actual == "demo":
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
                row["identity_evidence"] = ["brand", "model", "listing_name", "url"]
                filtered.append(row)

            result = AdapterResult(
                source_name=self.source_name,
                listings=filtered,
                status="live",
                latency_ms=int((time.monotonic() - started) * 1000),
                query_url=" | ".join(fetched_urls),
                error=partial_error,
            )
            record_adapter_execution(
                self.source_name,
                success=True,
                latency_ms=result.latency_ms,
            )
            return result
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            error = str(exc)[:300]
            record_adapter_execution(
                self.source_name,
                success=False,
                latency_ms=latency_ms,
                error=error,
            )
            return AdapterResult(
                source_name=self.source_name,
                status="unavailable",
                latency_ms=latency_ms,
                error=error,
                query_url=url,
            )


def _health_snapshot(source_name: str) -> dict[str, Any] | None:
    if not registry_db_enabled():
        return None
    try:
        with registry_connect() as conn, conn.cursor() as cur:
            cur.execute(
                """select sa.status, sa.circuit_state, sa.next_retry_at
                     from public.source_adapters sa
                     join public.sources s on s.source_id=sa.source_id
                    where s.name=%s and sa.status='verified'
                    order by sa.updated_at desc limit 1""",
                (source_name,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def adapter_execution_allowed(source_name: str) -> bool:
    health = _health_snapshot(source_name)
    if not health:
        return True
    if health.get("status") != "verified":
        return False
    state = str(health.get("circuit_state") or "closed")
    if state in {"closed", "half_open"}:
        return True
    retry_at = health.get("next_retry_at")
    if state == "open" and retry_at:
        from datetime import datetime, timezone
        return retry_at <= datetime.now(timezone.utc)
    return False


def record_adapter_execution(
    source_name: str,
    *,
    success: bool,
    latency_ms: int | None = None,
    error: str | None = None,
    failure_threshold: int = 3,
    cooldown_minutes: int = 15,
) -> None:
    if not registry_db_enabled():
        return
    with registry_connect() as conn, conn.cursor() as cur:
        adapter_filter = """select sa.adapter_id
                              from public.source_adapters sa
                              join public.sources s on s.source_id=sa.source_id
                             where s.name=%s and sa.status='verified'
                             order by sa.updated_at desc limit 1"""
        if success:
            cur.execute(
                f"""update public.source_adapters
                       set consecutive_failures=0,total_successes=total_successes+1,
                           last_success_at=now(),last_latency_ms=%s,last_error=null,
                           circuit_state='closed',circuit_opened_at=null,
                           next_retry_at=null,updated_at=now()
                     where adapter_id=({adapter_filter})""",
                (latency_ms, source_name),
            )
        else:
            cur.execute(
                f"""update public.source_adapters
                       set consecutive_failures=consecutive_failures+1,
                           total_failures=total_failures+1,last_failure_at=now(),
                           last_error=%s,last_latency_ms=%s,
                           circuit_state=case when consecutive_failures+1 >= %s
                                              then 'open' else circuit_state end,
                           circuit_opened_at=case when consecutive_failures+1 >= %s
                                                 then now() else circuit_opened_at end,
                           next_retry_at=case when consecutive_failures+1 >= %s
                                              then now()+make_interval(mins => %s)
                                              else next_retry_at end,
                           updated_at=now()
                     where adapter_id=({adapter_filter})""",
                (str(error or "")[:500], latency_ms, failure_threshold,
                 failure_threshold, failure_threshold, cooldown_minutes,
                 source_name),
            )
        conn.commit()


def build_verified_adapters(
    registry: list[dict[str, Any]],
) -> list[BuiltinMarketplaceAdapter]:
    """Build adapters for every source explicitly enabled for live search.

    Source eligibility is controlled by the registry; runtime failures are
    handled independently by the adapter health/circuit-breaker layer.
    """
    return [
        BuiltinMarketplaceAdapter(source)
        for source in registry
        if source.get("adapter_status") == "live"
        and source.get("enabled", True) is not False
    ]


def _image_coverage(listings: list[dict[str, Any]]) -> tuple[int, float]:
    """Return count and percentage of listings carrying at least one photo."""
    if not listings:
        return 0, 0.0
    with_images = sum(1 for listing in listings if listing.get("image") or listing.get("images"))
    return with_images, round(with_images * 100.0 / len(listings), 1)


def execute_adapters(
    request: AdapterRequest,
    registry: list[dict[str, Any]],
    *,
    max_workers: int = 8,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    adapters = build_verified_adapters(registry)
    if not adapters:
        return [], []

    results: list[AdapterResult] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(adapters))) as pool:
        future_to_adapter = {
            pool.submit(adapter.fetch, request): adapter for adapter in adapters
        }
        for future in as_completed(future_to_adapter):
            adapter = future_to_adapter[future]
            try:
                results.append(future.result())
            except Exception as exc:
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
        listings_with_images, image_coverage_pct = _image_coverage(result.listings)
        status = {
            "source": result.source_name,
            "status": result.status,
            "listings_found": len(result.listings),
            "listings_with_images": listings_with_images,
            "image_coverage_pct": image_coverage_pct,
            "query_url": result.query_url,
            "source_type": source.get("source_type"),
            "query_strategy": source.get("query_strategy"),
            "latency_ms": result.latency_ms,
        }
        if result.error:
            status["error"] = result.error
        statuses.append(status)

    return vehicles, statuses
