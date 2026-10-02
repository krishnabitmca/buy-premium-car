import unittest
from unittest.mock import patch

from src.source_intelligence import infer_segments, load_source_registry, plan_sources, summarize_plan


class TestSourceIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_source_registry(from_database=False)

    def test_registry_is_segmented_and_non_empty(self):
        self.assertGreaterEqual(len(self.registry), 20)
        for source in self.registry:
            self.assertTrue(source.get("name"))
            self.assertTrue(source.get("source_type"))
            self.assertTrue(source.get("conditions"))
            self.assertTrue(source.get("segments"))
            self.assertIn(source.get("adapter_status"), {"live", "candidate", "discovery_only"})

    def test_bmw_used_prioritizes_brand_and_used_sources(self):
        plan = plan_sources(brand="BMW", model="X5", condition="used", budget_min=30, budget_max=40,
                            destination="Bengaluru", registry=self.registry)
        names = [p["name"] for p in plan]
        self.assertIn("BMW Premium Selection", names)
        self.assertIn("CarDekho Used", names)
        self.assertIn("CarWale Used", names)
        self.assertLess(names.index("BMW Premium Selection"), names.index("CarDekho Used"))

    def test_bmw_demo_changes_source_mix(self):
        plan = plan_sources(brand="BMW", model="X5", condition="demo", budget_min=50, budget_max=80,
                            destination="Bengaluru", registry=self.registry)
        names = [p["name"] for p in plan]
        self.assertIn("BMW Premium Selection", names)
        self.assertIn("Motozite Demo", names)
        self.assertNotIn("CarDekho Used", names)
        self.assertNotIn("Spinny Luxury Used", names)

    def test_destination_does_not_filter_inventory_universe(self):
        india = plan_sources(brand="Toyota", model="Fortuner", condition="used",
                             destination="Bengaluru", registry=self.registry)
        no_destination = plan_sources(brand="Toyota", model="Fortuner", condition="used",
                                      destination=None, registry=self.registry)
        self.assertEqual({x["name"] for x in india}, {x["name"] for x in no_destination})

    def test_budget_infers_multiple_segments_when_range_crosses_boundary(self):
        self.assertEqual(infer_segments(30, 40), {"premium", "luxury"})

    def test_summary_separates_live_and_candidate_sources(self):
        plan = plan_sources(brand="BMW", model="X5", condition="used", budget_min=30, budget_max=40,
                            registry=self.registry)
        summary = summarize_plan(plan)
        self.assertEqual(summary["selected_sources"], summary["live_sources"] + summary["candidate_sources"])
        self.assertGreater(summary["candidate_sources"], 0)
        self.assertGreater(summary["live_sources"], 0)


    def test_model_capability_matrix_excludes_unverified_model(self):
        registry = [
            {
                "name": "BMW Specialist",
                "url": "https://example.in",
                "source_type": "marketplace",
                "adapter_status": "live",
                "geography": "india",
                "conditions": ["used"],
                "segments": ["luxury"],
                "brands": ["BMW"],
                "priority": 90,
                "query_strategy": "brand_model",
                "model_capabilities": [
                    {"brand": "BMW", "model": "3 Series", "condition": "used", "supported": True}
                ],
            }
        ]
        plan = plan_sources(
            brand="BMW", model="X5", condition="used",
            registry=registry, live_only=True
        )
        self.assertEqual(plan, [])

    def test_model_capability_matrix_accepts_verified_model_and_condition(self):
        registry = [
            {
                "name": "BMW Specialist",
                "url": "https://example.in",
                "source_type": "marketplace",
                "adapter_status": "live",
                "geography": "india",
                "conditions": ["used", "demo"],
                "segments": ["luxury"],
                "brands": ["BMW"],
                "priority": 90,
                "query_strategy": "brand_model",
                "model_capabilities": [
                    {"brand": "BMW", "model": "X5", "condition": "used", "supported": True}
                ],
            }
        ]
        used = plan_sources(
            brand="BMW", model="X5", condition="used",
            registry=registry, live_only=True
        )
        demo = plan_sources(
            brand="BMW", model="X5", condition="demo",
            registry=registry, live_only=True
        )
        self.assertEqual(len(used), 1)
        self.assertEqual(demo, [])

    def test_brand_only_search_does_not_require_model_capability(self):
        registry = [
            {
                "name": "BMW Specialist",
                "url": "https://example.in",
                "source_type": "marketplace",
                "adapter_status": "live",
                "geography": "india",
                "conditions": ["used"],
                "segments": ["luxury"],
                "brands": ["BMW"],
                "priority": 90,
                "query_strategy": "brand_model",
                "model_capabilities": [],
            }
        ]
        plan = plan_sources(
            brand="BMW", model=None, condition="used",
            registry=registry, live_only=True
        )
        self.assertEqual(len(plan), 1)

    def test_database_registry_is_preferred_when_available(self):
        database_registry = [{"name": "Database Source", "source_type": "marketplace",
                              "adapter_status": "live", "conditions": ["used"],
                              "segments": ["premium"], "brands": ["all"]}]
        with patch("src.source_registry_db.enabled", return_value=True),              patch("src.source_registry_db.load_registry", return_value=database_registry):
            registry = load_source_registry(from_database=True)
        self.assertEqual(registry, database_registry)

    def test_yaml_remains_explicit_recovery_path(self):
        registry = load_source_registry(from_database=False)
        self.assertTrue(any(x["name"] == "CarDekho Used" for x in registry))


    def test_validated_discovered_source_is_candidate_until_adapter_is_verified(self):
        registry = [
            {
                "name": "Discovered - bmw-example.in",
                "url": "https://bmw-example.in/used-cars",
                "source_type": "marketplace",
                "adapter_status": "candidate",
                "geography": "india",
                "conditions": ["used"],
                "segments": ["luxury"],
                "brands": ["BMW"],
                "priority": 80,
                "query_strategy": "discovered_catalogue",
            },
        ]
        candidate_plan = plan_sources(
            brand="BMW",
            model="X5",
            condition="used",
            budget_min=30,
            budget_max=40,
            destination="Bengaluru",
            registry=registry,
        )
        self.assertEqual(len(candidate_plan), 1)
        self.assertEqual(candidate_plan[0]["name"], "Discovered - bmw-example.in")
        self.assertEqual(candidate_plan[0]["adapter_status"], "candidate")
        self.assertEqual(candidate_plan[0]["query"], "BMW X5 used")

        live_plan = plan_sources(
            brand="BMW",
            model="X5",
            condition="used",
            registry=registry,
            live_only=True,
        )
        self.assertEqual(live_plan, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
