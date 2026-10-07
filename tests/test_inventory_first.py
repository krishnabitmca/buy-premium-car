import unittest
from unittest.mock import patch

from src.inventory_db import search_inventory


class TestInventoryFirstSearch(unittest.TestCase):
    @patch("src.inventory_db._connect")
    def test_inventory_search_reads_latest_verified_observation(self, connect):
        class Cursor:
            def execute(self, sql, params):
                self.sql = sql
                self.params = params
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def fetchall(self):
                return [{
                    "brand": "BMW",
                    "model": "X5",
                    "price_lakh": 72.0,
                    "source": "CarDekho",
                    "live_verified": True,
                }]
        class Conn:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def cursor(self): return Cursor()
        connect.return_value = Conn()

        with patch.dict("os.environ", {"SOURCE_INTELLIGENCE_DATABASE_URL": "postgres://test"}):
            rows, sources = search_inventory(query="BMW X5", condition="used")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model"], "X5")
        self.assertEqual(sources[0]["mode"], "inventory")
        self.assertEqual(rows[0]["offers"][0]["source"], "CarDekho")
        self.assertEqual(rows[0]["source_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
