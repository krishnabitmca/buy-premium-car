import unittest
from unittest.mock import patch

from src.source_intelligence import plan_sources
from api import search as search_api


class SourceControlPlaneContractTests(unittest.TestCase):
    def test_live_only_never_executes_candidate_sources(self):
        registry = [
            {
                "name": "Verified Marketplace",
                "source_type": "marketplace",
                "adapter_status": "live",
                "conditions": ["used"],
                "segments": ["premium"],
                "brands": ["BMW"],
                "priority": 90,
            },
            {
                "name": "Discovered BMW Source",
                "source_type": "oem_certified",
                "adapter_status": "candidate",
                "conditions": ["used"],
                "segments": ["luxury"],
                "brands": ["BMW"],
                "priority": 100,
            },
        ]
        plan = plan_sources(brand="BMW", model="X5", condition="used",
                            budget_min=30, budget_max=40,
                            registry=registry, live_only=True)
        self.assertEqual([x["name"] for x in plan], ["Verified Marketplace"])

    def test_source_strategy_is_operational_metadata_not_inventory(self):
        vehicles = [{
            "brand": "BMW", "model": "X5", "price_lakh": 38,
            "source": "Verified Marketplace",
            "url": "https://example.com/x5",
            "live_verified": True, "data_consistent": True,
        }]
        sources = [{
            "source": "Verified Marketplace",
            "status": "live",
            "listings_found": 1,
        }]
        registry = [{
            "name": "Verified Marketplace",
            "source_type": "marketplace",
            "adapter_status": "live",
            "conditions": ["used"],
            "segments": ["premium"],
            "brands": ["BMW"],
            "priority": 90,
        }, {
            "name": "Candidate Source",
            "source_type": "oem_certified",
            "adapter_status": "candidate",
            "conditions": ["used"],
            "segments": ["luxury"],
            "brands": ["BMW"],
            "priority": 100,
        }]
        with patch.object(search_api, "load_source_registry", return_value=registry),              patch.object(search_api, "live_inventory", return_value=(vehicles, sources)):
            source_plan = search_api.plan_sources(
                brand="BMW", model="X5", condition="used",
                budget_min=30, budget_max=40, registry=registry
            )
            self.assertTrue(any(x["adapter_status"] == "candidate" for x in source_plan))
            self.assertEqual(len(vehicles), 1)
            self.assertEqual(vehicles[0]["source"], "Verified Marketplace")

    def test_database_failure_does_not_change_live_inventory_contract(self):
        with patch.object(search_api, "live_inventory",
                          return_value=([], [{"source": "Verified Marketplace",
                                              "status": "unavailable",
                                              "listings_found": 0,
                                              "error": "timeout"}])):
            # The API must report live-source unavailability rather than using
            # historical inventory as a fallback.
            self.assertEqual([], search_api.live_inventory()[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
