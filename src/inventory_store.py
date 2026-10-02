from __future__ import annotations

"""Persistence bridge from normalized crawler Vehicles to PostgreSQL inventory."""

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable

from .models import Vehicle
from .source_registry_db import _connect, enabled as db_enabled


def _listing_key(vehicle: Vehicle) -> str:
    raw = vehicle.final_url or vehicle.url
    return hashlib.sha256(raw.strip().lower().encode()).hexdigest()[:40]


def _identity_key(vehicle: Vehicle) -> str | None:
    # Fingerprints are intentionally provisional. They are useful for continuity,
    # but are not treated as proof that two listings are the same physical vehicle.
    if not vehicle.fingerprint or not vehicle.brand or not vehicle.model:
        return None
    return f"provisional:{vehicle.fingerprint}"


def _condition(vehicle: Vehicle) -> str:
    value = str(vehicle.condition_signal or "").strip().lower()
    if value in {"demo", "demonstrator"}:
        return "demo"
    if value == "used":
        return "used"
    text = f"{vehicle.title} {vehicle.variant} {vehicle.source_name}".lower()
    return "demo" if "demo" in text or "demonstrator" in text else "unknown"


def _date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def persist_vehicles(vehicles: Iterable[Vehicle]) -> int:
    if not db_enabled():
        return 0

    rows = list(vehicles)
    persisted = 0

    with _connect() as conn, conn.cursor() as cur:
        for vehicle in rows:
            cur.execute(
                "select source_id from public.sources where name=%s limit 1",
                (vehicle.source_name,),
            )
            source = cur.fetchone()
            if not source:
                # A discovered source may not have been promoted into the source
                # registry yet. Do not invent a foreign key.
                continue
            source_id = source["source_id"]
            identity_key = _identity_key(vehicle)
            condition = _condition(vehicle)

            vehicle_id = None
            if identity_key:
                cur.execute(
                    """select vehicle_id
                       from public.vehicles
                       where identity_key=%s
                         and identity_state='provisional'
                       limit 1""",
                    (identity_key,),
                )
                existing = cur.fetchone()
                vehicle_id = existing["vehicle_id"] if existing else None

            if vehicle_id:
                cur.execute(
                    """update public.vehicles set
                       variant=coalesce(%s,variant),
                       manufacture_year=coalesce(%s,manufacture_year),
                       registration_year=coalesce(%s,registration_year),
                       manufacture_date=coalesce(%s,manufacture_date),
                       registration_date=coalesce(%s,registration_date),
                       condition=case when condition='unknown' then %s else condition end,
                       fuel=coalesce(%s,fuel),
                       transmission=coalesce(%s,transmission),
                       seller_city=coalesce(%s,seller_city),
                       seller_state=coalesce(%s,seller_state),
                       registration_state=coalesce(%s,registration_state),
                       status='active',
                       identity_confidence=greatest(identity_confidence,%s),
                       last_seen_at=now(),updated_at=now()
                       where vehicle_id=%s""",
                    (
                        vehicle.variant, vehicle.year_manufacture,
                        vehicle.year_registration, _date(vehicle.manufacture_date),
                        _date(vehicle.registration_date), condition,
                        vehicle.fuel, vehicle.transmission, vehicle.seller_city,
                        vehicle.seller_state, vehicle.registration_state,
                        float(vehicle.identity_confidence or 0), vehicle_id,
                    ),
                )
            else:
                cur.execute(
                    """insert into public.vehicles
                       (identity_key,brand,model,variant,manufacture_year,
                        registration_year,manufacture_date,registration_date,
                        condition,fuel,transmission,seller_city,seller_state,
                        registration_state,status,identity_confidence,
                        metadata)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                               'active',%s,%s)
                       returning vehicle_id""",
                    (
                        identity_key, vehicle.brand, vehicle.model, vehicle.variant,
                        vehicle.year_manufacture, vehicle.year_registration,
                        _date(vehicle.manufacture_date), _date(vehicle.registration_date),
                        condition, vehicle.fuel, vehicle.transmission,
                        vehicle.seller_city, vehicle.seller_state,
                        vehicle.registration_state,
                        float(vehicle.identity_confidence or 0),
                        json.dumps({"identity_state": "provisional"}),
                    ),
                )
                vehicle_id = cur.fetchone()["vehicle_id"]

            listing_key = _listing_key(vehicle)
            cur.execute(
                """insert into public.listings
                   (source_id,vehicle_id,source_listing_key,url,final_url,title,
                    seller_city,seller_state,condition,status,last_seen_at,
                    last_verified_at,metadata)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',now(),now(),%s)
                   on conflict (source_id,source_listing_key) do update set
                     vehicle_id=excluded.vehicle_id,url=excluded.url,
                     final_url=excluded.final_url,title=excluded.title,
                     seller_city=excluded.seller_city,seller_state=excluded.seller_state,
                     condition=excluded.condition,status='active',
                     last_seen_at=now(),last_verified_at=now(),
                     updated_at=now(),metadata=excluded.metadata
                   returning listing_id""",
                (
                    source_id, vehicle_id, listing_key, vehicle.url, vehicle.final_url,
                    vehicle.title, vehicle.seller_city, vehicle.seller_state,
                    condition,
                    json.dumps({
                        "source_tier": vehicle.source_tier,
                        "live_verified": bool(vehicle.live_verified),
                    }),
                ),
            )
            listing_id = cur.fetchone()["listing_id"]

            cur.execute(
                """insert into public.vehicle_observations
                   (vehicle_id,listing_id,source_id,observed_at,price_lakh,
                    mileage_km,owner_count,manufacture_year,registration_year,
                    seller_city,seller_state,registration_state,live_verified,
                    data_consistent,sold_signal,identity_confidence,snapshot)
                   values (%s,%s,%s,now(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    vehicle_id, listing_id, source_id, vehicle.price_lakh,
                    vehicle.mileage_km, vehicle.owner_count,
                    vehicle.year_manufacture, vehicle.year_registration,
                    vehicle.seller_city, vehicle.seller_state,
                    vehicle.registration_state, bool(vehicle.live_verified),
                    bool(vehicle.data_consistent), bool(vehicle.sold_signal),
                    float(vehicle.identity_confidence or 0),
                    json.dumps(vehicle.to_dict(), default=str, ensure_ascii=False),
                ),
            )
            persisted += 1

        conn.commit()
    return persisted
