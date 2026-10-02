from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import live_marketplaces as lm


def test_catalog_rejects_navigation_links():
    selected = {
        "name": "BMW",
        "url": "https://www.cardekho.com/bmw-cars",
    }
    assert not lm._is_current_model_link(selected, "https://www.cardekho.com/bmw/gallery")
    assert not lm._is_current_model_link(selected, "https://www.cardekho.com/bmw/images")
    assert not lm._is_current_model_link(selected, "https://www.cardekho.com/bmw/reviews")
    assert lm._is_current_model_link(selected, "https://www.cardekho.com/bmw/x5")


def test_catalog_rejects_brand_name_as_model():
    selected = {
        "name": "Audi",
        "url": "https://www.cardekho.com/cars/Audi",
    }
    assert lm._canonical_brand("Audi").lower() == "audi"
    assert lm._canonical_brand("Audi").lower() != "q5"
