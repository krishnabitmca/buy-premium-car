from __future__ import annotations

"""Optional PostgreSQL persistence for CarScanner source intelligence."""

import json
import os
from typing import Any, Iterable
from urllib.parse import urlparse

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


def database_url() -> str | None:
    return os.getenv("SOURCE_INTELLIGENCE_DATABASE_URL") or os.getenv("DATABASE_URL")


def enabled() -> bool:
    return bool(database_url())


def _connect():
    if psycopg is None:
        raise RuntimeError("PostgreSQL is configured but psycopg is not installed")
    return psycopg.connect(database_url(), row_factory=dict_row)


def source_key(source: dict[str, Any]) -> str:
    return str(
        source.get("source_key")
        or source.get("name")
        or urlparse(str(source.get("url") or "")).netloc
    ).strip().lower().replace(" ", "_")


def sync_registry(sources: Iterable[dict[str, Any]]) -> int:
    if not enabled():
        return 0
    rows = list(sources)
    with _connect() as conn:
        with conn.cursor() as cur:
            for source in rows:
                key = source_key(source)
                metadata = {
                    k: v for k, v in source.items()
                    if k not in {"name", "url", "tier", "source_type", "adapter_status",
                                 "geography", "query_strategy", "vehicle_link_pattern",
                                 "priority", "brands", "conditions", "segments"}
                }
                cur.execute(
                    """insert into public.sources
                    (source_key,name,url,tier,source_type,adapter_status,geography,
                     query_strategy,vehicle_link_pattern,priority,enabled,metadata)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s)
                    on conflict (source_key) do update set
                      name=excluded.name,url=excluded.url,tier=excluded.tier,
                      source_type=excluded.source_type,adapter_status=excluded.adapter_status,
                      geography=excluded.geography,query_strategy=excluded.query_strategy,
                      vehicle_link_pattern=excluded.vehicle_link_pattern,
                      priority=excluded.priority,enabled=true,last_seen_at=now(),
                      metadata=excluded.metadata
                    returning source_id""",
                    (key, source.get("name"), source.get("url"), int(source.get("tier", 2)),
                     source.get("source_type", "unknown"), source.get("adapter_status", "candidate"),
                     source.get("geography", "india"), source.get("query_strategy", "brand_model"),
                     source.get("vehicle_link_pattern"), int(source.get("priority", 50)),
                     json.dumps(metadata))
                )
                source_id = cur.fetchone()["source_id"]
                for capability_type, values in (
                    ("brand", source.get("brands") or []),
                    ("condition", source.get("conditions") or []),
                    ("segment", source.get("segments") or []),
                ):
                    for value in values:
                        cur.execute(
                            """insert into public.source_capabilities
                               (source_id,capability_type,capability_value)
                               values (%s,%s,%s)
                               on conflict do nothing""",
                            (source_id, capability_type, str(value))
                        )
                cur.execute(
                    """insert into public.source_endpoints
                       (source_id,url,endpoint_type,is_active)
                       values (%s,%s,'catalogue',true)
                       on conflict (source_id,url) do update set is_active=true""",
                    (source_id, source.get("url"))
                )
        conn.commit()
    return len(rows)


def load_registry() -> list[dict[str, Any]]:
    if not enabled():
        return []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """select s.*,
               coalesce(jsonb_agg(distinct sc.capability_value) filter
                 (where sc.capability_type='brand'),'[]') as brands,
               coalesce(jsonb_agg(distinct sc.capability_value) filter
                 (where sc.capability_type='condition'),'[]') as conditions,
               coalesce(jsonb_agg(distinct sc.capability_value) filter
                 (where sc.capability_type='segment'),'[]') as segments,
               coalesce((
                 select jsonb_agg(jsonb_build_object(
                   'brand', smc.brand,
                   'model', smc.model,
                   'condition', smc.condition,
                   'supported', smc.supported,
                   'query_template', smc.query_template,
                   'listing_count', smc.listing_count,
                   'freshness_minutes', smc.freshness_minutes,
                   'last_verified_at', smc.last_verified_at
                 ) order by smc.brand, smc.model, smc.condition)
                 from public.source_model_capabilities smc
                 where smc.source_id=s.source_id
               ), '[]') as model_capabilities
               from public.sources s
               left join public.source_capabilities sc on sc.source_id=s.source_id
               where s.enabled=true
               group by s.source_id
               order by s.priority desc, s.name"""
        )
        rows = cur.fetchall()
    result = []
    for row in rows:
        item = dict(row)
        for key in ("brands", "conditions", "segments", "model_capabilities"):
            item[key] = list(item.get(key) or [])
        result.append(item)
    return result


def record_discoveries(discoveries: Iterable[dict[str, Any]]) -> int:
    if not enabled():
        return 0
    rows = list(discoveries)
    with _connect() as conn, conn.cursor() as cur:
        for item in rows:
            cur.execute(
                """insert into public.source_discoveries
                   (domain,url,title,snippet,query,source_type,condition,segment,
                    brand_hint,candidate_confidence,status)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'discovered')
                   on conflict (domain,url) do update set
                     title=excluded.title,snippet=excluded.snippet,query=excluded.query,
                     source_type=excluded.source_type,condition=excluded.condition,
                     segment=excluded.segment,brand_hint=excluded.brand_hint,
                     candidate_confidence=excluded.candidate_confidence""",
                (item.get("domain"), item.get("url"), item.get("title"), item.get("snippet"),
                 item.get("query"), item.get("source_type"), item.get("condition"),
                 item.get("segment"), item.get("brand_hint"), item.get("candidate_confidence"))
            )
        conn.commit()
    return len(rows)


def record_health(source_name: str, *, status: str, http_status: int | None = None,
                  latency_ms: int | None = None, listings_found: int = 0,
                  parser_ok: bool | None = None, inventory_verified: bool | None = None,
                  error_message: str | None = None) -> None:
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """insert into public.source_health
               (source_id,status,http_status,latency_ms,listings_found,parser_ok,
                inventory_verified,error_message)
               select source_id,%s,%s,%s,%s,%s,%s,%s
               from public.sources where name=%s""",
            (status, http_status, latency_ms, listings_found, parser_ok,
             inventory_verified, error_message, source_name)
        )
        cur.execute(
            "update public.sources set last_validated_at=now() where name=%s",
            (source_name,)
        )
        conn.commit()


def promote_discovery(discovery: dict[str, Any], *, listings_found: int) -> str | None:
    """Promote a validated discovery into the live source registry.

    Promotion is deliberately evidence-based: the caller must have fetched the
    endpoint and proven that it exposes extractable inventory before calling
    this function. Existing YAML/DB sources are never overwritten by a discovery.
    """
    if not enabled() or listings_found < 2:
        return None

    url = str(discovery.get("url") or "").strip()
    domain = str(discovery.get("domain") or urlparse(url).netloc).lower().removeprefix("www.")
    if not url or not domain:
        return None

    brand = str(discovery.get("brand_hint") or "").strip()
    condition = str(discovery.get("condition") or "both").strip().lower()
    segment = str(discovery.get("segment") or "mass_market").strip().lower()
    source_type = str(discovery.get("source_type") or "marketplace").strip().lower()
    name = f"Discovered - {domain}"
    key = f"discovered_{domain.replace('.', '_').replace('-', '_')}"

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """select source_id, name from public.sources
               where lower(regexp_replace(url, '^https?://(www\\.)?', '')) like %s
                  or source_key=%s
               limit 1""",
            (domain + "%", key),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """update public.sources
                   set last_seen_at=now(), last_validated_at=now()
                   where source_id=%s""",
                (existing["source_id"],),
            )
            cur.execute(
                """insert into public.source_adapters
                   (source_id,adapter_key,adapter_type,status,query_strategy,
                    supports_brand,supports_model,supports_condition,supports_location,
                    metadata)
                   values (%s,%s,'discovered_catalogue','draft','discovered_catalogue',
                           %s,%s,true,false,%s)
                   on conflict (adapter_key) do nothing""",
                (
                    existing["source_id"],
                    key + "_discovered",
                    bool(brand),
                    True,
                    json.dumps({"validation_listings_found": listings_found,
                                "requires_adapter_verification": True}),
                ),
            )
            cur.execute(
                """update public.source_discoveries
                   set source_id=%s,status='validated'
                   where domain=%s and url=%s""",
                (existing["source_id"], domain, url),
            )
            conn.commit()
            return str(existing["name"])

        metadata = {
            "discovered": True,
            "discovery_title": discovery.get("title"),
            "discovery_query": discovery.get("query"),
            "candidate_confidence": discovery.get("candidate_confidence"),
            "validation_listings_found": listings_found,
        }
        cur.execute(
            """insert into public.sources
               (source_key,name,url,tier,source_type,adapter_status,geography,
                query_strategy,vehicle_link_pattern,priority,enabled,metadata)
               values (%s,%s,%s,2,%s,'candidate','india','discovered_catalogue',
                       '/(?:used|pre-owned|demo|cars|vehicle|listing)[^?#]*',
                       %s,true,%s)
               returning source_id""",
            (key, name, url, source_type, 75 + min(15, int(float(discovery.get("candidate_confidence") or 0) * 10)),
             json.dumps(metadata)),
        )
        source_id = cur.fetchone()["source_id"]

        capabilities = [
            ("brand", brand or "all"),
            ("condition", condition if condition in {"used", "demo"} else "both"),
            ("segment", segment),
        ]
        for capability_type, capability_value in capabilities:
            cur.execute(
                """insert into public.source_capabilities
                   (source_id,capability_type,capability_value)
                   values (%s,%s,%s)
                   on conflict do nothing""",
                (source_id, capability_type, capability_value),
            )
        cur.execute(
            """insert into public.source_endpoints
               (source_id,url,endpoint_type,is_active,last_checked_at,
                last_http_status,metadata)
               values (%s,%s,'catalogue',true,now(),200,%s)
               on conflict (source_id,url) do update set
                 is_active=true,last_checked_at=now(),last_http_status=200""",
            (source_id, url, json.dumps({"validated_listings": listings_found})),
        )
        cur.execute(
            """insert into public.source_adapters
               (source_id,adapter_key,adapter_type,status,query_strategy,
                supports_brand,supports_model,supports_condition,supports_location,
                metadata)
               values (%s,%s,'discovered_catalogue','draft','discovered_catalogue',
                       %s,%s,true,false,%s)
               on conflict (adapter_key) do nothing""",
            (
                source_id,
                key + "_discovered",
                bool(brand),
                True,
                json.dumps({"validation_listings_found": listings_found,
                            "requires_adapter_verification": True}),
            ),
        )
        cur.execute(
            """update public.source_discoveries
               set source_id=%s,status='promoted'
               where domain=%s and url=%s""",
            (source_id, domain, url),
        )
        cur.execute(
            """insert into public.source_health
               (source_id,status,http_status,listings_found,parser_ok,inventory_verified,metadata)
               values (%s,'healthy',200,%s,true,true,%s)""",
            (source_id, listings_found, json.dumps({"promotion": "discovery_validation"})),
        )
        conn.commit()
    return name
