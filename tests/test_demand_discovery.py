import unittest

from src.discovery import build_query_bank


class TestDemandDrivenDiscovery(unittest.TestCase):
    def test_demand_intent_adds_model_specific_queries(self):
        queries = build_query_bank(
            {"brands": [], "all_india": True, "source_types": []},
            demand=[{
                "brand": "BMW",
                "model": "X5",
                "condition": "used",
                "destination_state": "karnataka",
            }],
        )
        self.assertIn('"BMW X5" used cars India', queries)
        self.assertIn('"BMW X5" used cars "karnataka"', queries)
        self.assertIn('"BMW X5" certified used cars India', queries)

    def test_demo_demand_adds_demo_specific_queries(self):
        queries = build_query_bank(
            {"brands": [], "all_india": True, "source_types": []},
            demand=[{
                "brand": "Mercedes-Benz",
                "model": "GLE",
                "condition": "demo",
                "destination_state": "delhi",
            }],
        )
        self.assertIn('"Mercedes-Benz GLE" demo cars India', queries)
        self.assertIn('"Mercedes-Benz GLE" demonstrator cars India', queries)
        self.assertIn('"Mercedes-Benz GLE" dealer demo India', queries)
        self.assertIn('"Mercedes-Benz GLE" test drive car for sale India', queries)

    def test_empty_demand_preserves_existing_query_bank(self):
        search = {
            "brands": ["BMW"],
            "all_india": True,
            "source_types": [],
            "queries_per_brand": 2,
        }
        queries = build_query_bank(search, demand=[])
        self.assertEqual(
            queries[:2],
            ['"BMW" "used car" India', '"BMW" "demo car" India'],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
