from __future__ import annotations

"""Canonical physical-vehicle identity evidence.

VIN/chassis is authoritative.  When it is unavailable we create a deterministic
candidate identity only when enough independent attributes agree.  The key is
source-agnostic so the same physical car can accumulate multiple provider offers.
"""

import hashlib
import re
from typing import Any

from .models import Vehicle


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def strong_identity(v: Vehicle) -> str | None:
    for value in (getattr(v, "vin", None), getattr(v, "chassis_number", None)):
        normalized = _norm(value)
        if len(normalized) >= 8:
            return "vin:" + normalized
    metadata = getattr(v, "metadata", None)
    if isinstance(metadata, dict):
        for key in ("vin", "vehicle_identification_number", "chassis_number"):
            value = _norm(metadata.get(key))
            if len(value) >= 8:
                return "vin:" + value
    return None


def candidate_identity(v: Vehicle) -> tuple[str | None, float, dict[str, Any]]:
    strong = strong_identity(v)
    if strong:
        return strong, 1.0, {"mode": "vin"}

    evidence: dict[str, Any] = {
        "brand": _norm(v.brand),
        "model": _norm(v.model),
        "variant": _norm(v.variant),
        "year": int(v.year_manufacture) if v.year_manufacture else None,
        "fuel": _norm(v.fuel),
        "transmission": _norm(v.transmission),
        "city": _norm(v.seller_city or v.location),
        "registration_state": _norm(v.registration_state),
        "mileage_bucket": int(round(int(v.mileage_km) / 500.0) * 500) if v.mileage_km is not None else None,
    }
    required = evidence["brand"] and evidence["model"] and evidence["year"]
    discriminators = sum(bool(evidence[k]) for k in ("variant", "fuel", "transmission", "city", "registration_state"))
    if not required or evidence["mileage_bucket"] is None or discriminators < 2:
        return None, 0.0, {"mode": "provisional", **evidence}

    raw = "|".join(str(evidence[k] or "") for k in (
        "brand", "model", "variant", "year", "fuel", "transmission",
        "city", "registration_state", "mileage_bucket"
    ))
    confidence = min(0.94, 0.72 + 0.04 * discriminators)
    return "candidate:" + hashlib.sha256(raw.encode("utf-8")).hexdigest(), confidence, {
        "mode": "candidate", **evidence
    }
