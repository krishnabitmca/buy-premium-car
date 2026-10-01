from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
import re

from ddgs import DDGS


@dataclass
class DiscoveryResult:
    url: str
    title: str
    snippet: str
    domain: str
    query: str
    source_type: str
    condition: str
    segment: str
    brand_hint: str | None
    candidate_confidence: float


SOURCE_QUERY_TEMPLATES = {
    "marketplace": [
        '"{brand}" used cars India marketplace',
        '"{brand}" second hand cars India',
        '"{brand}" pre owned cars India',
    ],
    "oem_certified": [
        '"{brand}" certified used cars India',
        '"{brand}" approved used cars India',
        '"{brand}" pre owned cars India dealer',
    ],
    "demo_dealer": [
        '"{brand}" demo cars India dealer',
        '"{brand}" demonstrator cars India',
        '"{brand}" dealer demo vehicle India',
    ],
    "luxury_specialist": [
        '"{brand}" luxury used cars India dealer',
        '"{brand}" premium pre owned cars India',
        '"{brand}" used luxury car dealer India',
    ],
    "classifieds": [
        '"{brand}" used cars India classifieds',
        '"{brand}" second hand cars owner India',
    ],
    "dealer_network": [
        '"{brand}" used car dealer India',
        '"{brand}" pre owned dealer India',
        '"{brand}" used cars dealership India',
    ],
}

GENERIC_SOURCE_QUERIES = [
    '"used cars" India marketplace',
    '"second hand cars" India marketplace',
    '"certified used cars" India OEM',
    '"pre owned cars" India dealer network',
    '"demo cars" India dealership',
    '"demonstrator cars" India dealer',
    '"luxury used cars" India dealer',
    '"premium used cars" India dealer',
    '"used cars" India classifieds',
    '"used cars" India multi brand dealer',
    '"used car" "dealer network" India',
    '"used cars" "certified" India',
]


def _segment_for_brand(brand: str) -> str:
    luxury = {
        "BMW", "Mercedes-Benz", "Audi", "Volvo", "Lexus", "Jaguar",
        "Land Rover", "Porsche", "Maserati", "Ferrari", "Lamborghini",
        "Aston Martin", "Bentley", "Rolls-Royce", "McLaren", "Lotus",
        "Mini", "MINI",
    }
    premium = {"Jeep", "Skoda", "Volkswagen", "Toyota", "BYD", "MG Motor", "MG"}
    if brand in luxury:
        return "luxury"
    if brand in premium:
        return "premium"
    return "mass_market"


def _classify(title: str, snippet: str, query: str, brand_hint: str | None) -> tuple[str, str, float]:
    blob = f"{title} {snippet} {query}".lower()
    if any(x in blob for x in ("demo car", "demo vehicle", "demonstrator", "demo cars")):
        condition = "demo"
    elif any(x in blob for x in ("used car", "second hand", "pre-owned", "pre owned", "certified used")):
        condition = "used"
    else:
        condition = "both"

    if any(x in blob for x in ("certified", "approved used", "oem")):
        source_type = "oem_certified"
    elif any(x in blob for x in ("dealer", "dealership", "showroom", "dealer network")):
        source_type = "dealer_network"
    elif any(x in blob for x in ("classified", "owner", "direct seller")):
        source_type = "classifieds"
    elif any(x in blob for x in ("luxury", "premium", "pre-owned luxury")):
        source_type = "luxury_specialist"
    elif any(x in blob for x in ("marketplace", "second hand cars", "used cars")):
        source_type = "marketplace"
    else:
        source_type = "unknown"

    confidence = 0.45
    if brand_hint and brand_hint.lower() in blob:
        confidence += 0.15
    if condition != "both":
        confidence += 0.10
    if source_type != "unknown":
        confidence += 0.20
    if any(x in blob for x in ("buy", "inventory", "cars for sale", "used cars")):
        confidence += 0.10
    return source_type, condition, min(1.0, confidence)


def build_query_bank(search):
    brands = list(search.get("brands", []))
    all_india = bool(search.get("all_india", True))
    city_hints = list(search.get("city_hints", []))
    queries_per_brand = max(1, int(search.get("queries_per_brand", 2)))
    city_hints_per_run = max(0, int(search.get("city_hints_per_run", 12)))
    configured_source_types = search.get("source_types")
    source_types = list(configured_source_types or [])
    query_bank = []

    # Preserve the original lightweight contract when callers do not opt into
    # the deep source-discovery profile. Production settings explicitly provide
    # source_types, which activates the broader archetype search.
    for brand in brands:
        if not all_india:
            continue
        if not source_types:
            query_bank.extend([
                f'"{brand}" "used car" India',
                f'"{brand}" "demo car" India',
            ][:queries_per_brand])
            continue

        # Deep discovery is deliberately multi-dimensional. We do not search
        # only "{brand} used car"; we search source archetypes separately so an
        # OEM certified site, dealer group, demo page, classifieds site, and
        # luxury specialist can all be discovered for the same brand.
        for source_type in source_types:
            templates = SOURCE_QUERY_TEMPLATES.get(source_type, [])
            for template in templates[:queries_per_brand]:
                query_bank.append(template.format(brand=brand))
        query_bank.extend([
            f'"{brand}" used car Bangalore dealer',
            f'"{brand}" used car Mumbai dealer',
            f'"{brand}" used car Delhi NCR dealer',
            f'"{brand}" demo car dealer India',
        ])

    # Generic source discovery finds multi-brand platforms that brand queries
    # can miss entirely.
    if all_india:
        query_bank.extend(GENERIC_SOURCE_QUERIES)

        # Local dealer discovery is intentionally sampled across many cities.
        for city in city_hints[:city_hints_per_run]:
            query_bank.extend([
                f'"used car" "{city}" dealer',
                f'"pre-owned car" "{city}" dealer',
                f'"demo car" "{city}" dealer',
                f'"luxury used car" "{city}" dealer',
            ])

    return list(dict.fromkeys(query_bank))


def _looks_like_source_landing(url: str, title: str, snippet: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    path = parsed.path.lower()
    blob = f"{title} {snippet} {path}".lower()
    listing_tokens = ("/used-car-details/", "/used/", "/cars/", "/listing/", "/vehicle/")
    # A result is a source candidate when it looks like a catalogue, dealer,
    # marketplace or program page rather than a single vehicle detail page.
    if any(token in path for token in listing_tokens) and not any(
        x in blob for x in ("used cars", "pre-owned", "cars for sale", "dealer", "certified")
    ):
        return False
    return any(
        x in blob for x in (
            "used cars", "second hand", "pre-owned", "certified", "approved",
            "demo cars", "dealer", "dealership", "marketplace", "cars for sale",
            "luxury cars", "pre owned",
        )
    )


def discover(settings, known_domains):
    results = []
    search = settings.search
    max_n = int(search.get("max_discovery_results_per_query", 8))
    engines = search.get("engines", ["bing", "duckduckgo", "google"])
    query_bank = build_query_bank(search)
    brands = list(search.get("brands", []))
    seen_domains = set(known_domains)
    seen_urls = set()

    for query in query_bank:
        try:
            with DDGS() as ddgs:
                for engine in engines:
                    try:
                        rows = ddgs.text(query, max_results=max_n, backend=engine)
                    except TypeError:
                        rows = ddgs.text(query, max_results=max_n)
                    except Exception as exc:
                        print(f"discovery backend {engine} failed: {exc}")
                        continue

                    for row in rows:
                        url = row.get("href") or row.get("url")
                        if not url or url in seen_urls:
                            continue
                        title = row.get("title", "")
                        snippet = row.get("body", row.get("snippet", ""))
                        if not _looks_like_source_landing(url, title, snippet):
                            continue

                        domain = urlparse(url).netloc.lower().removeprefix("www.")
                        if not domain:
                            continue

                        brand_hint = next(
                            (b for b in brands if re.search(r"\b" + re.escape(b) + r"\b", f"{title} {snippet}", re.I)),
                            None,
                        )
                        source_type, condition, confidence = _classify(
                            title, snippet, query, brand_hint
                        )
                        segment = _segment_for_brand(brand_hint) if brand_hint else (
                            "luxury" if "luxury" in f"{title} {snippet}".lower()
                            else "mass_market"
                        )

                        seen_urls.add(url)
                        # Keep known domains in discovery output only when they
                        # reveal a new source URL/classification. Never enqueue a
                        # known domain as a new crawler source.
                        if domain in seen_domains:
                            continue

                        results.append(DiscoveryResult(
                            url=url,
                            title=title,
                            snippet=snippet,
                            domain=domain,
                            query=query,
                            source_type=source_type,
                            condition=condition,
                            segment=segment,
                            brand_hint=brand_hint,
                            candidate_confidence=confidence,
                        ))
                        seen_domains.add(domain)
        except Exception as exc:
            print(f"discovery query failed: {query}: {exc}")

    # Prefer high-confidence source candidates and keep one representative URL
    # per domain. The actual crawler remains responsible for verifying whether
    # the source has extractable inventory before it becomes a live adapter.
    return sorted(
        results,
        key=lambda x: (-x.candidate_confidence, x.source_type, x.domain),
    )
