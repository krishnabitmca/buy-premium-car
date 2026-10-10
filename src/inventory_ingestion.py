from __future__ import annotations

"""Transactional ingestion into canonical vehicle -> listings -> observations."""

import hashlib
import json
from .models import Vehicle
from .source_registry_db import _connect, enabled
from .canonical_identity import candidate_identity


def _listing_key(v: Vehicle) -> str:
    raw=str(v.final_url or v.url or "").strip()
    if not raw:
        raw=f"{v.source_name}|{v.title}|{v.price_lakh}|{v.mileage_km}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ingest_vehicles(vehicles: list[Vehicle]) -> dict[str,int]:
    if not enabled() or not vehicles:
        return {"vehicles":0,"listings":0,"observations":0}
    counts={"vehicles":0,"listings":0,"observations":0}
    with _connect() as conn,conn.cursor() as cur:
        for v in vehicles:
            # Explicit negative evidence updates an existing offer, even if its
            # price/identity fields are no longer present on the sold page.
            if v.sold_signal:
                cur.execute(
                    """select l.listing_id,l.vehicle_id,l.source_id
                       from public.listings l join public.sources s on s.source_id=l.source_id
                       where s.name=%s and l.source_listing_key=%s
                       for update of l""",
                    (str(v.source_name or "").strip(), _listing_key(v)),
                )
                listing=cur.fetchone()
                if listing and listing["vehicle_id"]:
                    cur.execute(
                        """update public.listings set status='sold',last_seen_at=now(),last_verified_at=now()
                           where listing_id=%s""", (listing["listing_id"],),
                    )
                    cur.execute(
                        """insert into public.vehicle_observations
                           (vehicle_id,listing_id,source_id,observed_at,price_lakh,
                            live_verified,data_consistent,sold_signal,snapshot)
                           values (%s,%s,%s,now(),%s,false,%s,true,%s)""",
                        (listing["vehicle_id"],listing["listing_id"],listing["source_id"],v.price_lakh,
                         bool(v.data_consistent),json.dumps({"url":v.url,"final_url":v.final_url,
                                                            "verification_notes":v.verification_notes})),
                    )
                    counts["listings"]+=1; counts["observations"]+=1
                continue
            if not v.live_verified or v.price_lakh is None or not v.brand or not v.model:
                continue
            cur.execute("select source_id from public.sources where name=%s and enabled=true limit 1",(str(v.source_name or "").strip(),))
            source=cur.fetchone()
            if not source: continue
            source_id=source["source_id"]; listing_key=_listing_key(v)
            identity_key,identity_confidence,evidence=candidate_identity(v)
            identity_state="confirmed" if identity_key and identity_key.startswith("vin:") else ("candidate" if identity_key else "provisional")

            vehicle_id=None
            if identity_key:
                cur.execute(
                    """select vehicle_id from public.vehicles
                       where identity_key=%s and identity_state in ('confirmed','candidate')
                       order by identity_confidence desc limit 1""",(identity_key,))
                match=cur.fetchone()
                if match: vehicle_id=match["vehicle_id"]

            if vehicle_id is None:
                provisional_key=identity_key or ("provisional:"+str(v.source_name).lower()+":"+listing_key)
                cur.execute(
                    """insert into public.vehicles
                       (identity_key,identity_state,identity_evidence,brand,model,variant,
                        manufacture_year,registration_year,manufacture_date,registration_date,
                        condition,fuel,transmission,seller_city,seller_state,registration_state,
                        status,identity_confidence,last_seen_at,updated_at,metadata)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                               'active',%s,now(),now(),%s)
                       on conflict do nothing returning vehicle_id""",
                    (provisional_key,identity_state,json.dumps(evidence),v.brand,v.model,v.variant,
                     v.year_manufacture,v.year_registration,v.manufacture_date,v.registration_date,
                     str(v.condition_signal or "used").lower() if str(v.condition_signal or "used").lower() in {"used","demo"} else "unknown",
                     v.fuel,v.transmission,v.seller_city,v.seller_state,v.registration_state,
                     max(float(v.identity_confidence),identity_confidence),
                     json.dumps({"identity_mode":evidence.get("mode"),"image_urls":list(v.image_urls or []),
                                 "vin":v.vin,"chassis_number":v.chassis_number,**dict(v.metadata or {})})))
                inserted=cur.fetchone()
                if inserted: vehicle_id=inserted["vehicle_id"]
                else:
                    cur.execute("select vehicle_id from public.vehicles where identity_key=%s order by created_at limit 1",(provisional_key,))
                    row=cur.fetchone()
                    if row: vehicle_id=row["vehicle_id"]
            if vehicle_id is None: continue
            counts["vehicles"]+=1

            cur.execute(
                """insert into public.listings
                   (source_id,vehicle_id,source_listing_key,url,final_url,title,seller_name,
                    seller_city,seller_state,condition,status,first_seen_at,last_seen_at,last_verified_at,metadata)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',now(),now(),now(),%s)
                   on conflict(source_id,source_listing_key) do update set
                     vehicle_id=excluded.vehicle_id,url=excluded.url,final_url=excluded.final_url,
                     title=excluded.title,seller_city=excluded.seller_city,seller_state=excluded.seller_state,
                     condition=excluded.condition,status='active',last_seen_at=now(),last_verified_at=now(),
                     metadata=excluded.metadata returning listing_id""",
                (source_id,vehicle_id,listing_key,v.url,v.final_url,v.title,None,v.seller_city,v.seller_state,
                 str(v.condition_signal or "used").lower() if str(v.condition_signal or "used").lower() in {"used","demo"} else "unknown",
                 json.dumps({"identity_confidence":max(float(v.identity_confidence),identity_confidence),
                  "identity_evidence":evidence,"image_urls":list(v.image_urls or []),
                  "verification_notes":v.verification_notes,"vin":v.vin,"chassis_number":v.chassis_number})))
            listing_id=cur.fetchone()["listing_id"]; counts["listings"]+=1
            cur.execute(
                """insert into public.vehicle_observations
                   (vehicle_id,listing_id,source_id,observed_at,price_lakh,mileage_km,owner_count,
                    manufacture_year,registration_year,seller_city,seller_state,registration_state,
                    live_verified,data_consistent,sold_signal,identity_confidence,snapshot)
                   values (%s,%s,%s,now(),%s,%s,%s,%s,%s,%s,%s,%s,true,%s,false,%s,%s)""",
                (vehicle_id,listing_id,source_id,v.price_lakh,v.mileage_km,v.owner_count,
                 v.year_manufacture,v.year_registration,v.seller_city,v.seller_state,v.registration_state,
                 bool(v.data_consistent),max(float(v.identity_confidence),identity_confidence),
                 json.dumps({"url":v.url,"final_url":v.final_url,"title":v.title,"source":v.source_name,
                  "condition":v.condition_signal,"identity_evidence":evidence,"vin":v.vin,"chassis_number":v.chassis_number})))
            counts["observations"]+=1
        conn.commit()
    return counts
