"""Conservative seller-state enrichment on positive inventory ingestion."""
from uuid import uuid4

import pytest

from src.inventory_ingestion import _seller_state_for_ingestion, ingest_vehicles
from src.models import Vehicle


def _vehicle(city=None, state=None):
    return Vehicle(
        source_name="Fixture", source_tier=1, url="https://example.invalid/car/1",
        title="BMW X5", brand="BMW", model="X5", price_lakh=40,
        live_verified=True, seller_city=city, seller_state=state,
    )


@pytest.mark.parametrize("city,expected", [
    ("Bangalore", "Karnataka"),
    ("Mumbai", "Maharashtra"),
    ("Bangalore, Karnataka", "Karnataka"),
    ("Delhi, Mumbai", None),
    ("Mulund (W), Mumbai", None),
    ("Goa", None),
    ("", None),
])
def test_infer_only_unambiguous_known_seller_city(city, expected):
    assert _seller_state_for_ingestion(_vehicle(city)) == expected


def test_explicit_seller_state_is_never_overridden():
    assert _seller_state_for_ingestion(_vehicle("Bangalore", "Haryana")) == "Haryana"


def test_positive_ingestion_persists_inferred_state_in_all_three_layers(monkeypatch):
    source_id, vehicle_id, listing_id = uuid4(), uuid4(), uuid4()
    inserts = {}

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            self.sql = sql
            if "insert into public." in sql:
                table = sql.split("insert into public.", 1)[1].split()[0]
                inserts[table] = params

        def fetchone(self):
            if "select source_id from public.sources" in self.sql:
                return {"source_id": source_id}
            if "insert into public.vehicles" in self.sql:
                return {"vehicle_id": vehicle_id}
            if "insert into public.listings" in self.sql:
                return {"listing_id": listing_id}
            return None

    class Conn:
        def cursor(self):
            return Cursor()

    monkeypatch.setattr("src.inventory_ingestion.enabled", lambda: True)
    result = ingest_vehicles([_vehicle("Bangalore")], _connection=Conn())
    assert result == {"vehicles": 1, "listings": 1, "observations": 1}
    assert inserts["vehicles"][14] == "Karnataka"
    assert inserts["listings"][8] == "Karnataka"
    assert inserts["vehicle_observations"][9] == "Karnataka"
