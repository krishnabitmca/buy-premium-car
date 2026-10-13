"""JSON boundary for inventory rows, retaining the existing numeric lakh API."""

from datetime import date, datetime, timezone
from decimal import Decimal
from math import isfinite
from typing import Any
from uuid import UUID


def json_inventory_value(value: Any) -> Any:
    """Convert known database types; unexpected objects remain serialization errors.

    Amounts remain numbers for existing web clients. A future versioned API can
    adopt integer paise without changing the legacy price_lakh field's type.
    """
    if isinstance(value, dict):
        return {key: json_inventory_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_inventory_value(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Inventory timestamps must include a timezone")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        number = float(value)
        if not isfinite(number):
            raise ValueError("Inventory numeric values must be finite")
        return number
    return value
