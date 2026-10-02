from __future__ import annotations

"""Source capability registry + customer-intent source planner.

This module deliberately separates:
1. source discovery/maintenance (the registry),
2. source selection (the planner), and
3. source execution (live marketplace adapters).

A source can therefore be known and highly relevant without being incorrectly
treated as live inventory until its adapter has been verified.
"""

from pathlib import Path
from typing import Any
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "sources.yaml"

SEGMENT_BY_MAX_LAKH = (
    (15.0, "mass_market"),
    (40.0, "premium"),
    (100.0, "luxury"),
    (float("inf"), "super_luxury"),
)


def load_source_registry(
    path: Path = REGISTRY_PATH,
    *,
    from_database: bool = True,
) -> list[dict[str, Any]]:
    # PostgreSQL is the production system of record. YAML remains the bootstrap
    # and deterministic local fallback.
    if from_database:
        try:
            from .source_registry_db import enabled, load_registry
            if enabled():
                database_sources = load_registry()
                if database_sources:
                    return database_sources
        except Exception:
            # Source search must remain available if the control-plane database
            # is temporarily unavailable; it must never invent inventory.
            pass
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return list(data.get("known_sources") or [])


def normalize_condition(value: Any) -> str:
    value = str(value or "both").strip().lower()
    if value in {"demonstrator", "demo", "demo car"}:
        return "demo"
    if value in {"used", "pre-owned", "preowned"}:
        return "used"
    return "both"


def infer_segments(budget_min: float | None, budget_max: float | None) -> set[str]:
    if budget_min is None and budget_max is None:
        return {"mass_market", "premium", "luxury", "super_luxury"}
    ceiling = budget_max if budget_max is not None else budget_min
    floor = budget_min if budget_min is not None else 0.0
    segments: set[str] = set()
    for limit, segment in SEGMENT_BY_MAX_LAKH:
        if floor <= limit and ceiling >= (0 if segment == "mass_market" else {
            "premium": 15.0,
            "luxury": 40.0,
            "super_luxury": 100.0,
        }.get(segment, 0)):
            segments.add(segment)
    return segments or {"premium"}


def _brand_matches(source: dict[str, Any], brand: str | None) -> bool:
    brands = [str(x).lower() for x in source.get("brands") or []]
    if not brand or not brands or "all" in brands:
        return True
    wanted = str(brand).strip().lower()
    return wanted in brands or wanted.replace(" ", "-") in brands


def _segment_matches(source: dict[str, Any], segments: set[str]) -> bool:
    supported = {str(x).lower() for x in source.get("segments") or []}
    return not supported or bool(supported & segments)


def _condition_matches(source: dict[str, Any], condition: str) -> bool:
    supported = {normalize_condition(x) for x in source.get("conditions") or []}
    if condition == "both":
        return bool(supported & {"used", "demo"}) or not supported
    return condition in supported


def _condition_bonus(source: dict[str, Any], condition: str) -> int:
    kind = str(source.get("source_type") or "").lower()
    strategy = str(source.get("query_strategy") or "").lower()
    if condition == "demo":
        if "oem" in kind or "dealer" in kind or "demo" in strategy:
            return 25
        if "classified" in kind:
            return -10
    if condition == "used" and ("marketplace" in kind or "retailer" in kind or "certified" in kind):
        return 8
    return 0


def _brand_bonus(source: dict[str, Any], brand: str | None) -> int:
    if not brand:
        return 0
    brands = {str(x).lower() for x in source.get("brands") or []}
    return 22 if str(brand).lower() in brands else 0


def _destination_bonus(source: dict[str, Any], destination: str | None) -> int:
    # Destination is never an inventory boundary. It only makes a regional
    # source more useful as a secondary search when the buyer names a city.
    if not destination:
        return 0
    return 5 if source.get("geography") == "regional" else 0



def _model_matches(source: dict[str, Any], brand: str | None, model: str | None, condition: str) -> bool:
    """Require verified source/model capability when a model is explicitly requested."""
    if not model:
        return True

    capabilities = source.get("model_capabilities") or []
    if not capabilities:
        # YAML/bootstrap sources have no matrix yet; preserve current fallback behavior.
        return True

    wanted_brand = str(brand or "*").strip().lower()
    wanted_model = str(model).strip().lower()
    wanted_condition = normalize_condition(condition)

    for cap in capabilities:
        if not cap.get("supported", True):
            continue
        cap_brand = str(cap.get("brand") or "").strip().lower()
        cap_model = str(cap.get("model") or "").strip().lower()
        cap_condition = normalize_condition(cap.get("condition"))
        if (cap_brand in {"*", wanted_brand}
                and cap_model in {"*", wanted_model}
                and cap_condition in {"both", wanted_condition}):
            return True
    return False

def plan_sources(
    *,
    brand: str | None = None,
    model: str | None = None,
    condition: str = "both",
    budget_min: float | None = None,
    budget_max: float | None = None,
    destination: str | None = None,
    registry: list[dict[str, Any]] | None = None,
    live_only: bool = False,
) -> list[dict[str, Any]]:
    """Return a ranked source plan without turning destination into a filter."""
    condition = normalize_condition(condition)
    registry = registry if registry is not None else load_source_registry()
    segments = infer_segments(budget_min, budget_max)
    plan = []

    for source in registry:
        if live_only and source.get("adapter_status") != "live":
            continue
        if not _condition_matches(source, condition):
            continue
        if not _brand_matches(source, brand):
            continue
        if not _model_matches(source, brand, model, condition):
            continue
        if not _segment_matches(source, segments):
            continue

        score = int(source.get("priority") or 50)
        score += _brand_bonus(source, brand)
        score += _condition_bonus(source, condition)
        score += _destination_bonus(source, destination)

        reasons = []
        if brand and str(brand).lower() in {str(x).lower() for x in source.get("brands") or []}:
            reasons.append("brand-specific source")
        elif brand:
            reasons.append("multi-brand coverage")
        if condition == "demo" and source.get("source_type") in {"oem_certified", "dealer_group"}:
            reasons.append("dealer/OEM demo relevance")
        if condition == "used" and source.get("source_type") in {"marketplace", "used_retailer"}:
            reasons.append("broad used inventory")
        if source.get("geography") == "regional":
            reasons.append("regional/dealer coverage")
        if source.get("adapter_status") == "live":
            reasons.append("live adapter available")
        else:
            reasons.append("candidate adapter")

        query_terms = []
        if brand:
            query_terms.append(brand)
        if model:
            query_terms.append(model)
        query_terms.append("demo" if condition == "demo" else "used")
        query = " ".join(query_terms)

        plan.append({
            "name": source.get("name"),
            "url": source.get("url"),
            "source_type": source.get("source_type"),
            "adapter_status": source.get("adapter_status", "candidate"),
            "geography": source.get("geography", "unknown"),
            "conditions": source.get("conditions") or [],
            "segments": source.get("segments") or [],
            "model_capabilities": source.get("model_capabilities") or [],
            "priority": int(source.get("priority") or 50),
            "score": score,
            "query_strategy": source.get("query_strategy", "brand_model"),
            "query": query,
            "reasons": reasons,
        })

    return sorted(plan, key=lambda x: (-x["score"], x["name"] or ""))


def summarize_plan(plan: list[dict[str, Any]]) -> dict[str, Any]:
    live = [x for x in plan if x.get("adapter_status") == "live"]
    candidates = [x for x in plan if x.get("adapter_status") != "live"]
    return {
        "selected_sources": len(plan),
        "live_sources": len(live),
        "candidate_sources": len(candidates),
        "live_source_names": [x["name"] for x in live],
        "candidate_source_names": [x["name"] for x in candidates],
    }
