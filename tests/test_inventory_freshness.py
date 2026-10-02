import unittest
from datetime import datetime, timedelta, timezone

from src.inventory_freshness import freshness_state, refresh_key, refresh_priority


class TestInventoryFreshness(unittest.TestCase):
    def test_fresh_aging_stale_expired(self):
        now = datetime(2026, 10, 2, tzinfo=timezone.utc)
        self.assertEqual(freshness_state(now - timedelta(hours=1), now=now), "fresh")
        self.assertEqual(freshness_state(now - timedelta(hours=10), now=now), "aging")
        self.assertEqual(freshness_state(now - timedelta(days=2), now=now), "stale")
        self.assertEqual(freshness_state(now - timedelta(days=8), now=now), "expired")
        self.assertEqual(freshness_state(None, now=now), "expired")

    def test_refresh_key_deduplicates_intent_dimensions(self):
        self.assertEqual(
            refresh_key("S1", "BMW", "X5", "USED", "Karnataka"),
            ("S1", "bmw", "x5", "used", "karnataka"),
        )

    def test_stale_high_demand_has_higher_priority(self):
        fresh = refresh_priority(search_count=100, inventory_hit_count=90, freshness="fresh")
        stale = refresh_priority(search_count=100, inventory_hit_count=90, freshness="stale")
        self.assertGreater(stale, fresh)


if __name__ == "__main__":
    unittest.main(verbosity=2)
