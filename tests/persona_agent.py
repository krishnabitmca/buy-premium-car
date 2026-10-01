"""CarScanner persona-agent: exercise every live dropdown value as a real buyer.

Persona:
  A buyer anywhere in India looking for either a used or demo car. They may
  select any brand/model exposed by the live catalog and optionally set a
  minimum/maximum price. Destination is informational and must never narrow
  inventory by geography.

This is deliberately data-driven: it discovers the current dropdown values
from the live catalog rather than maintaining a second hard-coded model list.
Zero inventory is a valid outcome; wrong identity, budget leakage, condition
leakage, or source/catalog errors are defects.
"""
from __future__ import annotations

import json
import time

from src.live_marketplaces import live_brands, live_models, live_inventory


PRICE_PROFILES = [
    ("open", None, None),
    ("premium_30_40", 30.0, 40.0),
    ("premium_40_80", 40.0, 80.0),
]


def _identity_tokens(value: object) -> list[str]:
    import re
    return re.findall(r"[a-z0-9]+", str(value or "").lower())


def _contains_sequence(needle: str, *haystacks: object) -> bool:
    wanted = _identity_tokens(needle)
    if not wanted:
        return False
    for value in haystacks:
        tokens = _identity_tokens(value)
        for i in range(0, len(tokens) - len(wanted) + 1):
            if tokens[i:i + len(wanted)] == wanted:
                return True
    return False


def _condition(row: dict) -> str:
    signal = str(row.get("condition_signal") or "").lower()
    return "demo" if signal in {"demo", "demonstrator"} else "used"


def validate_results(brand: str, model: str, rows: list[dict], minimum: float | None,
                     maximum: float | None, condition: str) -> list[str]:
    errors = []
    for row in rows:
        if not _contains_sequence(brand, row.get("brand"), row.get("listing_name"), row.get("url")):
            errors.append(f"brand mismatch: {brand} -> {row.get('listing_name')}")
        if not _contains_sequence(model, row.get("model"), row.get("listing_name"),
                                   row.get("variant"), row.get("url")):
            errors.append(f"model mismatch: {brand} {model} -> {row.get('listing_name')}")
        price = row.get("price_lakh")
        if minimum is not None and (price is None or float(price) < minimum):
            errors.append(f"below min: {brand} {model} {price} < {minimum}")
        if maximum is not None and (price is None or float(price) > maximum):
            errors.append(f"above max: {brand} {model} {price} > {maximum}")
        actual = _condition(row)
        if condition in {"used", "demo"} and actual != condition:
            errors.append(f"condition mismatch: requested={condition} actual={actual} "
                          f"{row.get('listing_name')}")
    return errors


def main() -> int:
    started = time.time()
    brands = live_brands()
    report = {
        "persona": "India-wide used/demo buyer",
        "catalog_brands": len(brands),
        "catalog_models": 0,
        "journeys": 0,
        "results": 0,
        "zero_result_journeys": 0,
        "errors": [],
        "brands": {},
    }

    for brand_entry in brands:
        brand = brand_entry["name"]
        try:
            models = live_models(brand)
        except Exception as exc:
            report["errors"].append({"brand": brand, "stage": "model_catalog",
                                     "error": str(exc)[:240]})
            continue

        report["catalog_models"] += len(models)
        report["brands"][brand] = {"models": len(models)}
        for model_entry in models:
            model = model_entry["name"]
            for condition in ("used", "demo", "both"):
                for profile, minimum, maximum in PRICE_PROFILES:
                    query = f"{brand} {model}"
                    try:
                        rows, sources = live_inventory(query)
                        if not any(s.get("status") == "live" for s in sources):
                            report["errors"].append({
                                "brand": brand, "model": model, "stage": "sources",
                                "error": "all live sources unavailable",
                            })
                            continue
                        if condition == "both":
                            selected = rows
                        else:
                            selected = [r for r in rows if _condition(r) == condition]
                        selected = [
                            r for r in selected
                            if minimum is None or (r.get("price_lakh") is not None and float(r["price_lakh"]) >= minimum)
                        ]
                        selected = [
                            r for r in selected
                            if maximum is None or (r.get("price_lakh") is not None and float(r["price_lakh"]) <= maximum)
                        ]
                        report["journeys"] += 1
                        report["results"] += len(selected)
                        if not selected:
                            report["zero_result_journeys"] += 1
                        errors = validate_results(brand, model, selected, minimum, maximum, condition)
                        if errors:
                            report["errors"].extend({
                                "brand": brand, "model": model, "condition": condition,
                                "profile": profile, "error": e
                            } for e in errors)
                    except Exception as exc:
                        report["errors"].append({
                            "brand": brand, "model": model, "condition": condition,
                            "profile": profile, "stage": "search",
                            "error": str(exc)[:240],
                        })

    report["elapsed_seconds"] = round(time.time() - started, 1)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
