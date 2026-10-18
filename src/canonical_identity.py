from __future__ import annotations

"""Canonical physical-vehicle identity evidence.

Only a full, format-checked VIN can provide a cross-source exact key. When no
identifier is supplied we create a deterministic
candidate identity only when enough independent attributes agree.  The key is
source-agnostic so the same physical car can accumulate multiple provider offers.
"""

import hashlib
import re
from typing import Any

from .models import Vehicle


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def normalized_full_vin(value: Any) -> str | None:
    """Conservative modern VIN syntax, not manufacturer/physical verification.

    Never strip masking or punctuation into a plausible VIN. Do not impose the
    US check digit on Indian/imported vehicles without manufacturer evidence.
    """
    text = str(value or '').strip().upper()
    if not re.fullmatch(r'[A-HJ-NPR-Z0-9]{17}', text):
        return None
    if not re.search(r'[A-Z]', text) or not re.search(r'[0-9]', text):
        return None
    if len(set(text)) <= 2 or re.search(r'X{4,}', text):
        return None
    return text.lower()


def identifier_evidence(v: Vehicle) -> tuple[str | None, dict[str, Any]]:
    supplied = [('vin', v.vin), ('chassis_number', v.chassis_number)]
    if isinstance(v.metadata, dict):
        supplied.extend(('metadata.'+key, v.metadata.get(key)) for key in
                        ('vin', 'vehicle_identification_number', 'chassis_number'))
    supplied = [(field, value) for field, value in supplied if str(value or '').strip()]
    valid = {normalized_full_vin(value) for _, value in supplied}
    valid.discard(None)
    provenance = {'identifier_fields': [field for field, _ in supplied],
                  'identity_policy': 'full-vin-v1'}
    if len(valid) > 1:
        return None, {**provenance, 'mode': 'conflict', 'reason': 'conflicting_full_identifiers'}
    if valid:
        return 'vin:'+next(iter(valid)), {**provenance, 'mode': 'vin',
                'validation': 'format_only', 'physical_identity_verified': False}
    return None, {**provenance, 'mode': 'provisional',
                  'reason': 'unsupported_or_partial_identifier' if supplied else 'identifier_absent'}


def strong_identity(v: Vehicle) -> str | None:
    return identifier_evidence(v)[0]


def candidate_identity(v: Vehicle) -> tuple[str | None, float, dict[str, Any]]:
    strong, identifiers = identifier_evidence(v)
    if strong:
        return strong, 1.0, identifiers
    if identifiers['reason'] != 'identifier_absent':
        # A partial/masked/conflicting identifier cannot become a shared key
        # indirectly through attribute buckets. Ingestion uses a source offer key.
        return None, 0.0, identifiers

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
