import unittest
from unittest.mock import patch

from src import live_marketplaces as lm


LIVE_REGISTRY = [
    {"name": "CarDekho Used", "url": "https://cardekho.example", "adapter_status": "live",
     "source_type": "marketplace", "conditions": ["used"], "segments": ["mass_market", "premium", "luxury"],
     "brands": ["all"], "priority": 90},
    {"name": "CarWale Used", "url": "https://carwale.example", "adapter_status": "live",
     "source_type": "marketplace", "conditions": ["used"], "segments": ["mass_market", "premium", "luxury"],
     "brands": ["all"], "priority": 90},
    {"name": "Cars24 Luxury Used", "url": "https://cars24.example", "adapter_status": "live",
     "source_type": "used_retailer", "conditions": ["used"], "segments": ["premium", "luxury"],
     "brands": ["BMW", "Mercedes-Benz", "Audi"], "priority": 82},
    {"name": "Spinny Luxury Used", "url": "https://spinny.example", "adapter_status": "live",
     "source_type": "used_retailer", "conditions": ["used"], "segments": ["premium", "luxury"],
     "brands": ["BMW", "Mercedes-Benz", "Audi"], "priority": 82},
    {"name": "BMW Premium Selection", "url": "https://bmw.example/buy-used-cars", "adapter_status": "live",
     "source_type": "oem_certified", "conditions": ["used", "demo"], "segments": ["luxury", "super_luxury"],
     "brands": ["BMW", "MINI"], "priority": 100,
     "demo_query_url_template": "https://bmw.example/buy-used-cars?models=demo_dealer_cars"},
    {"name": "BMW Premium Selection", "url": "https://bmw.example/buy-used-cars", "adapter_status": "live",
     "source_type": "oem_certified", "conditions": ["used", "demo"], "segments": ["luxury", "super_luxury"],
     "brands": ["BMW", "MINI"], "priority": 100,
     "demo_query_url_template": "https://bmw.example/buy-used-cars?models=demo_dealer_cars"},
    {"name": "Motozite Demo", "url": "https://motozite.example/demo-cars", "adapter_status": "live",
     "source_type": "luxury_specialist", "conditions": ["demo"],
     "segments": ["premium", "luxury", "super_luxury"],
     "brands": ["Mercedes-Benz", "BMW", "Audi"], "priority": 86},
    # Candidates must never be executed merely because they are relevant.
    {"name": "Audi Approved Plus", "url": "https://audi.example", "adapter_status": "candidate",
     "source_type": "oem_certified", "conditions": ["used", "demo"],
     "segments": ["luxury"], "brands": ["Audi"], "priority": 100},
]


class TestSearchPermutationMatrix(unittest.TestCase):
    def _selected_sources(self, query, condition="both", budget_min=None, budget_max=None, destination=None):
        captured = {}

        def fake_execute(request, registry, *, max_workers):
            captured["request"] = request
            captured["registry"] = registry
            captured["max_workers"] = max_workers
            return [], [{"source": s["name"], "status": "live", "listings_found": 0}
                        for s in registry]

        with patch.object(lm, "_live_source_entries", return_value=LIVE_REGISTRY),              patch("src.source_adapters.execute_adapters", side_effect=fake_execute):
            lm.live_inventory(query, condition, budget_min, budget_max, destination)
        return [s["name"] for s in captured["registry"]]

    def test_used_brand_only_bmw_hits_all_applicable_used_sources(self):
        self.assertEqual(set(self._selected_sources("BMW", "used")), {"CarDekho Used", "CarWale Used", "Cars24 Luxury Used", "Spinny Luxury Used"})

    def test_used_brand_only_audi_hits_all_applicable_used_sources(self):
        self.assertEqual(set(self._selected_sources("Audi", "used")), {"CarDekho Used", "CarWale Used", "Cars24 Luxury Used", "Spinny Luxury Used"})

    def test_demo_brand_only_audi_hits_demo_source_only(self):
        self.assertEqual(self._selected_sources("Audi", "demo"), ["Motozite Demo"])

    def test_demo_brand_only_bmw_includes_bmw_premium_selection(self):
        self.assertEqual(self._selected_sources("BMW", "demo"), ["BMW Premium Selection", "Motozite Demo"])

    def test_bmw_demo_uses_explicit_demo_route(self):
        urls = lm._targeted_source_urls("BMW", "demo", registry=LIVE_REGISTRY)
        self.assertEqual(urls["BMW Premium Selection"], "https://bmw.example/buy-used-cars?models=demo_dealer_cars")

    def test_demo_brand_only_bmw_includes_bmw_premium_selection(self):
        self.assertEqual(self._selected_sources("BMW", "demo"), ["BMW Premium Selection", "Motozite Demo"])

    def test_bmw_demo_uses_explicit_demo_route(self):
        urls = lm._targeted_source_urls("BMW", "demo", registry=LIVE_REGISTRY)
        self.assertEqual(urls["BMW Premium Selection"], "https://bmw.example/buy-used-cars?models=demo_dealer_cars")

    def test_both_brand_only_audi_includes_used_and_demo(self):
        self.assertEqual(set(self._selected_sources("Audi", "both")), {"CarDekho Used", "CarWale Used", "Cars24 Luxury Used", "Spinny Luxury Used", "Motozite Demo"})

    def test_selected_model_audi_q5_keeps_all_applicable_sources(self):
        self.assertEqual(set(self._selected_sources("Audi Q5", "used")), {"CarDekho Used", "CarWale Used", "Cars24 Luxury Used", "Spinny Luxury Used"})

    def test_selected_model_mercedes_c_class_used_excludes_demo_only_source(self):
        self.assertEqual(set(self._selected_sources("Mercedes-Benz C-Class", "used")), {"CarDekho Used", "CarWale Used", "Cars24 Luxury Used", "Spinny Luxury Used"})

    def test_selected_model_demo_includes_demo_source(self):
        self.assertEqual(self._selected_sources("Mercedes-Benz C-Class", "demo"), ["Motozite Demo"])

    def test_budget_segment_excludes_luxury_retailers_from_mass_market_search(self):
        self.assertEqual(
            self._selected_sources("BMW", "used", budget_min=5, budget_max=10),
            ["CarDekho Used", "CarWale Used"],
        )

    def test_premium_budget_includes_luxury_retailers(self):
        self.assertEqual(set(self._selected_sources("BMW", "used", budget_min=30, budget_max=40)), {"CarDekho Used", "CarWale Used", "Cars24 Luxury Used", "Spinny Luxury Used"})

    def test_open_ended_budget_does_not_drop_luxury_sources(self):
        self.assertEqual(set(self._selected_sources("Audi", "used", budget_min=30, budget_max=None)), {"CarDekho Used", "CarWale Used", "Cars24 Luxury Used", "Spinny Luxury Used"})

    def test_destination_changes_priority_not_inventory_boundary(self):
        bengaluru = self._selected_sources("Audi", "used", destination="Bengaluru")
        delhi = self._selected_sources("Audi", "used", destination="Delhi")
        self.assertEqual(bengaluru, delhi)

    def test_candidate_oem_source_is_never_executed(self):
        selected = self._selected_sources("Audi", "used")
        self.assertNotIn("Audi Approved Plus", selected)

    def test_unknown_brand_does_not_execute_brand_specific_luxury_sources(self):
        self.assertEqual(
            self._selected_sources("Toyota", "used"),
            ["CarDekho Used", "CarWale Used"],
        )

    def test_source_plan_does_not_change_when_destination_is_interstate(self):
        local = self._selected_sources("BMW X5", "used", destination="Bengaluru")
        interstate = self._selected_sources("BMW X5", "used", destination="Delhi")
        self.assertEqual(local, interstate)


if __name__ == "__main__":
    unittest.main()
