import unittest
from unittest.mock import patch

from src.inventory_ingestion import _listing_key
from src.canonical_identity import candidate_identity
from src.inventory_refresh_worker import claim_jobs
from src.models import Vehicle


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
