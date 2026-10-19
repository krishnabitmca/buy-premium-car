import unittest
from unittest.mock import patch

from src.inventory_ingestion import _listing_key, ingest_vehicles, AcceptedObservation
from src.canonical_identity import candidate_identity
from src.inventory_refresh_worker import claim_jobs
from src.models import Vehicle
from uuid import uuid4
from dataclasses import FrozenInstanceError
import pytest


def test_optional_membership_is_immutable_and_has_no_inventory_payload():
    record=AcceptedObservation(uuid4(),uuid4(),7,'positive')
    assert set(record.__dataclass_fields__)=={'source_id','listing_id','observation_id','evidence_kind'}
    with pytest.raises(FrozenInstanceError):
        record.observation_id=9


def test_failed_owned_commit_never_extends_accepted_collector(monkeypatch):
    source_id,listing_id,vehicle_id=uuid4(),uuid4(),uuid4()
    class Cursor:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def execute(self,sql,params):self.sql=sql
        def fetchone(self):
            if 'returning observation_id' in self.sql:return {'observation_id':42}
            return dict(source_id=source_id,listing_id=listing_id,vehicle_id=vehicle_id)
    class Conn:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def cursor(self):return Cursor()
        def commit(self):raise RuntimeError('commit failed')
    monkeypatch.setattr('src.inventory_ingestion.enabled',lambda:True)
    monkeypatch.setattr('src.inventory_ingestion._connect',lambda:Conn())
    accepted=[]
    row=Vehicle(source_name='Fixture',source_tier=1,url='https://fixture.invalid/car',title='Sold',sold_signal=True)
    with pytest.raises(RuntimeError,match='commit failed'):
        ingest_vehicles([row],_accepted_observations=accepted)
    assert accepted==[]


class TestInventoryIngestion(unittest.TestCase):
    def test_listing_key_is_stable(self):
        class V:
            url = "https://example.com/car/123"
            final_url = None
            source_name = "Example"
            title = "BMW X5"
            price_lakh = 70
            mileage_km = 20000
        self.assertEqual(_listing_key(V()), _listing_key(V()))

    def test_weak_identity_evidence_stays_provisional(self):
        v = Vehicle(
            source_name="CarDekho", source_tier=2,
            title="BMW X5", brand="BMW", model="X5",
            price_lakh=70, mileage_km=20000,
            url="https://cardekho.example/x5/1",
        )
        key, confidence, evidence = candidate_identity(v)
        self.assertIsNone(key)
        self.assertEqual(confidence, 0)
        self.assertEqual(evidence["mode"], "provisional")

    @patch("src.inventory_refresh_worker._connect")
    def test_claim_uses_skip_locked(self, connect):
        class Cursor:
            def execute(self, sql, params): self.sql = sql
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def fetchall(self): return []
        class Conn:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def cursor(self):
                self._cursor = Cursor()
                return self._cursor
            def commit(self): pass
        connect.return_value=Conn()
        with patch.dict("os.environ", {"SOURCE_INTELLIGENCE_DATABASE_URL":"postgres://test"}):
            self.assertEqual(claim_jobs(5), [])
        self.assertIn("skip locked", connect.return_value._cursor.sql.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
