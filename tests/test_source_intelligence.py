import unittest

from src.source_intelligence import (
    infer_segments,
    load_source_registry,
    plan_sources,
)


class TestSourceIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_source_registry()

    def test_registry_is_segmented_and_non_empty(self):
        self.assertGreaterEqual(len(self.registry), 20)
        for source in self.registry:
            self.assertTrue(source.get("name"))
            self.assertTrue(source.get("source_type"))
            self.assertTrue(source.get("conditions"))
            self.assertTrue(source.get("segments"))
            self.assertIn(source.get("adapter_status"), {"live", "candidate", "discovery_only"})

    def test_bmw_used_prioritizes_brand_and_used_sources(self):
        plan = plan_sources(
            brand="BMW",
            model="X5",
            condition="used",
            budget_min=30,
            budget_max=40,
            destination="Bengaluru",
            registry=self.registry,
        )
        names = [p["name"] for p in plan]
        self.assertIn("BMW Premium Selection", names)
        self.assertIn("CarDekho Used", names)
        self.assertIn("CarWale Used", names)
        self.assertLess(names.index("BMW Premium Selection"), names.index("CarDekho Used"))

    def test_bmw_demo_changes_source_mix(self):
        plan = plan_sources(
            brand="BMW",
            model="X5",
            condition="demo",
            budget_min=50,
            budget_max=80,
            destination="Bengaluru",
            registry=self.registry,
        )
        names = [p["name"] for p in plan]
        self.assertIn("BMW Premium Selection", names)
        self.assertIn("Motozite Demo", names)
        self.assertNotIn("CarDekho Used", names)
        self.assertNotIn("Spinny Luxury Used", names)

    def test_destination_does_not_filter_inventory_universe(self):
        india = plan_sources(
            brand="Toyota",
            model="Fortuner",
            condition="used",
            destination="Bengaluru",
            registry=self.registry,
        )
        no_destination = plan_sources(
            brand="Toyota",
            model="Fortuner",
            condition="used",
            destination=None,
            registry=self.registry,
        )
        self.assertEqual(
            {x["name"] for x in india},
            {x["name"] for x in no_destination},
        )

    def test_budget_infers_multiple_segments_when_range_crosses_boundary(self):
        self.assertEqual(infer_segments(30, 40), {"premium", "luxury"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
