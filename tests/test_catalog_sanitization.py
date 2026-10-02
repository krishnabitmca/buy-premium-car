import unittest
from unittest.mock import patch

from src import live_marketplaces as lm


class TestCatalogSanitization(unittest.TestCase):
    def test_navigation_slugs_are_not_models(self):
        selected={"name":"BMW","url":"https://www.cardekho.com/bmw-cars"}
        self.assertFalse(lm._is_current_model_link(selected,"https://www.cardekho.com/bmw/gallery"))
        self.assertFalse(lm._is_current_model_link(selected,"https://www.cardekho.com/bmw/images"))
        self.assertFalse(lm._is_current_model_link(selected,"https://www.cardekho.com/bmw/reviews"))
        self.assertTrue(lm._is_current_model_link(selected,"https://www.cardekho.com/bmw/x5"))

    def test_navigation_labels_are_not_model_names(self):
        for label in ("Images","Gallery","Photos","Videos","Reviews","Offers","Dealers"):
            self.assertIsNotNone(lm._clean_model_catalog_name(label))
            self.assertFalse(
                lm._is_current_model_link(
                    {"name":"BMW","url":"https://www.cardekho.com/bmw-cars"},
                    f"https://www.cardekho.com/bmw/{label.lower()}"
                )
            )

    def test_live_models_drops_navigation_artifacts(self):
        html="""
        <a href="/bmw/x1">BMW X1</a>
        <a href="/bmw/x5">BMW X5</a>
        <a href="/bmw/gallery">Images</a>
        <a href="/bmw/reviews">Reviews</a>
        <a href="/bmw/dealers">Dealers</a>
        """
        with patch.object(lm, "live_brands", return_value=[
            {"name":"BMW","slug":"bmw","url":"https://www.cardekho.com/bmw-cars","catalog_verified":"true"}
        ]), patch.object(lm, "fetch_text", return_value=html):
            models=lm.live_models("BMW")
        self.assertEqual([m["name"] for m in models], ["BMW X1","BMW X5"])

    def test_live_models_deduplicates_model_links(self):
        html="""
        <a href="/bmw/x5">BMW X5</a>
        <a href="/bmw/x5#overview">BMW X5</a>
        <a href="/carmodels/bmw/x5">BMW X5</a>
        """
        with patch.object(lm, "live_brands", return_value=[
            {"name":"BMW","slug":"bmw","url":"https://www.cardekho.com/bmw-cars","catalog_verified":"true"}
        ]), patch.object(lm, "fetch_text", return_value=html):
            models=lm.live_models("BMW")
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["name"], "BMW X5")


if __name__ == "__main__":
    unittest.main()
