"""Versioned traversal evidence, deliberately without absence authority.

A checkpoint identifies one configuration and intent, not a complete marketplace.
Only successful background batches publish this evidence with canonical ingestion.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

CONTRACT_VERSION = 1
ADAPTER_VERSION = "builtin-traversal-v1"


def scan_scope(source, request, roots):
    metadata = source.get("metadata") or {}
    # Include acquisition configuration, not secrets/session material or runtime
    # health. Any configuration change starts a new, explicitly scoped generation.
    keys = ("parser_strategy", "parser_version", "query_url_template",
            "brand_query_url_template", "city_catalog_path_pattern",
            "city_catalog_title_pattern", "catalogue_link_pattern")
    scope = {
        "source": str(source.get("source_id") or source.get("name") or ""),
        "query": " ".join(request.query.split()).casefold(),
        "condition": str(request.condition).casefold(),
        "destination": str(request.destination or "").strip().casefold(),
        "budget_min": request.budget_min, "budget_max": request.budget_max,
        "roots": sorted(set(roots)), "adapter_version": ADAPTER_VERSION,
        "configuration": {key: source.get(key) or metadata.get(key) for key in keys},
    }
    fingerprint = sha256(json.dumps(scope, sort_keys=True, separators=(",", ":"),
                                    default=str).encode()).hexdigest()
    return scope, fingerprint


def can_resume(previous, fingerprint):
    return (isinstance(previous, dict)
            and previous.get("contract_version") == CONTRACT_VERSION
            and previous.get("scope_fingerprint") == fingerprint
            and bool(previous.get("generation_id")) and bool(previous.get("started_at")))


def generation(progress, fingerprint):
    previous = progress.get("scan_generation") or {}
    if can_resume(previous, fingerprint):
        return dict(previous)
    return {"contract_version": CONTRACT_VERSION,
            "generation_id": str(uuid4()), "scope_fingerprint": fingerprint,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "resumed_legacy_checkpoint": bool(progress)}


def outcome(scan_generation, *, pending, background):
    # No adapter currently supplies reviewed enumeration/membership proof.
    # Exhausting advertised links is never an authority to remove unseen stock.
    return {**scan_generation,
            "execution_state": "batch_succeeded",
            "terminal_reason": "pending_pages" if pending else "frontier_exhausted",
            "coverage_state": "partial_traversal" if pending else "traversal_exhausted_unverified",
            "completeness_verified": False,
            "absence_reconciliation_permitted": False,
            "background_scan": background}
