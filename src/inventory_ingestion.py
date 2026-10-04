from __future__ import annotations

"""Transactional ingestion from normalized crawler vehicles into Supabase inventory.

Identity policy is intentionally conservative:
- source listing identity is always unique per source.
- a cross-source physical vehicle is merged only when a strong identity token
  (currently VIN/chassis metadata) is present.
- otherwise the vehicle remains provisional rather than risking false merges.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from .models import Vehicle
from .source_registry_db import _connect, enabled


def _listing_key(v: Vehicle) -> str:
    raw = str(v.final_url or v.url or "").strip()
    if not raw:
        raw = f"{v.source_name}|{v.title}|{v.price_lakh}|{v.mileage_km}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _strong_identity(v: Vehicle) -> str | None:
    metadata = getattr(v, "metadata", None)
    if isinstance(metadata, dict):
        for key in ("vin", "vehicle_identification_number", "chassis_number"):
            value = str(metadata.get(key) or "").strip().lower()
            if value and len(re.sub(r"[^a-z0-9]", "", value)) >= 8:
                return re.sub(r"[^a-z0-9]", "", value)
    return None


def _identity_key(v: Vehicle, listing_key: str) -> str:
    strong = _strong_identity(v)
    if strong:
        return "vin:" + strong
    # Provisional identity deliberately includes source listing identity. This
    # prevents false cross-marketplace merges until stronger evidence exists.
    return "provisional:" + v.source_name.strip().lower() + ":" + listing_key


def ingest_vehicles(vehicles: list[Vehicle]) -> dict[str, int]:
    """Upsert verified observations transactionally. Returns ingestion counters."""
    if not enabled() or not vehicles:
        return {"vehicles": 0, "listings": 0, "observations": 0}

    counts = {"vehicles": 0, "listings": 0, "observations": 0}
    with _connect() as conn, conn.cursor() as cur:
        for v in vehicles:
            if not v.live_verified or v.sold_signal or v.price_lakh is None:
                continue
            if not v.brand or not v.model:
                continue

            source_name = str(v.source_name or "").strip()
            cur.execute(
                "select source_id from public.sources where name=%s and enabled=true limit 1",
                (source_name,),
            )
            source = cur.fetchone()
            if not source:
                continue
            source_id = source["source_id"]
            listing_key = _listing_key(v)
            identity_key = _identity_key(v, listing_key)

            cur.execute(
                """insert into public.vehicles
                   (identity_key,brand,model,variant,manufacture_year,registration_year,
                    manufacture_date,registration_date,condition,fuel,transmission,
                    seller_city,seller_state,registration_state,status,
                    identity_confidence,last_seen_at,updated_at,metadata)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',
                           %s,now(),now(),%s)
                   on conflict(identity_key) do update set
                     variant=coalesce(excluded.variant,public.vehicles.variant),
                     manufacture_year=coalesce(excluded.manufacture_year,public.vehicles.manufacture_year),
                     registration_year=coalesce(excluded.registration_year,public.vehicles.registration_year),
                     fuel=coalesce(excluded.fuel,public.vehicles.fuel),
                     transmission=coalesce(excluded.transmission,public.vehicles.transmission),
                     seller_city=coalesce(excluded.seller_city,public.vehicles.seller_city),
                     seller_state=coalesce(excluded.seller_state,public.vehicles.seller_state),
                     status='active',last_seen_at=now(),updated_at=now()
                   returning vehicle_id""",
                (
                    identity_key, v.brand, v.model, v.variant, v.year_manufacture,
                    v.year_registration, v.manufacture_date, v.registration_date,
                    str(v.condition_signal or "used").lower()
                    if str(v.condition_signal or "used").lower() in {"used","demo"} else "unknown",
                    v.fuel, v.transmission, v.seller_city, v.seller_state,
                    v.registration_state, float(v.identity_confidence),
                    {"identity_mode": "strong" if _strong_identity(v) else "provisional",
                     "image_urls": list(v.image_urls or [])},
                ),
            )
            vehicle_id = cur.fetchone()["vehicle_id"]
            counts["vehicles"] += 1

            cur.execute(
                """insert into public.listings
                   (source_id,vehicle_id,source_listing_key,url,final_url,title,
                    seller_name,seller_city,seller_state,condition,status,
                    first_seen_at,last_seen_at,last_verified_at,metadata)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',
                           now(),now(),now(),%s)
                   on conflict(source_id,source_listing_key) do update set
                     vehicle_id=excluded.vehicle_id,url=excluded.url,final_url=excluded.final_url,
                     title=excluded.title,seller_city=excluded.seller_city,
                     seller_state=excluded.seller_state,condition=excluded.condition,
                     status='active',last_seen_at=now(),last_verified_at=now(),
                     metadata=excluded.metadata
                   returning listing_id""",
                (
                    source_id, vehicle_id, listing_key, v.url, v.final_url, v.title,
                    None, v.seller_city, v.seller_state,
                    str(v.condition_signal or "used").lower()
                    if str(v.condition_signal or "used").lower() in {"used","demo"} else "unknown",
                    {"identity_confidence": v.identity_confidence,
                     "verification_notes": v.verification_notes},
                ),
            )
            listing_id = cur.fetchone()["listing_id"]
            counts["listings"] += 1

            cur.execute(
                """insert into public.vehicle_observations
                   (vehicle_id,listing_id,source_id,observed_at,price_lakh,mileage_km,
                    owner_count,manufacture_year,registration_year,seller_city,
                    seller_state,registration_state,live_verified,data_consistent,
                    sold_signal,identity_confidence,snapshot)
                   values (%s,%s,%s,now(),%s,%s,%s,%s,%s,%s,%s,%s,true,%s,false,%s,%s)""",
                (
                    vehicle_id, listing_id, source_id, v.price_lakh, v.mileage_km,
                    v.owner_count, v.year_manufacture, v.year_registration,
                    v.seller_city, v.seller_state, v.registration_state,
                    bool(v.data_consistent), float(v.identity_confidence),
                    {"url": v.url, "final_url": v.final_url, "title": v.title,
                     "source": v.source_name, "condition": v.condition_signal},
                ),
            )
            counts["observations"] += 1
        conn.commit()
    return counts
