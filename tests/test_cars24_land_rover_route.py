"""Regression tests for the reviewed Cars24 Land Rover catalogue route.

These are deterministic routing tests; they do not certify live inventory,
availability, or source parser output.
"""
from src.live_marketplaces import _targeted_source_urls
from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter
from src.source_intelligence import load_source_registry


def _cars24_source():
    return next(
        source for source in load_source_registry(from_database=False)
        if source["name"] == "Cars24 Luxury Used"
    )


def test_land_rover_range_rover_uses_cars24_verified_land_rover_slug():
    source = _cars24_source()
    expected = "https://www.cars24.com/buy-used-landrover-range-rover-cars/"
    assert source["brand_slug_overrides"]["Land Rover"] == "landrover"
    assert _targeted_source_urls(
        "Land Rover Range Rover", "used", registry=[source]
    )["Cars24 Luxury Used"] == expected
    assert BuiltinMarketplaceAdapter(source)._urls(
        AdapterRequest(query="Land Rover Range Rover", condition="used")
    )[0] == expected


def test_land_rover_brand_only_and_other_brands_keep_correct_routes():
    source = _cars24_source()
    assert _targeted_source_urls(
        "Land Rover", "used", registry=[source]
    )["Cars24 Luxury Used"] == "https://www.cars24.com/buy-used-landrover-cars/"
    assert _targeted_source_urls(
        "BMW X5", "used", registry=[source]
    )["Cars24 Luxury Used"] == "https://www.cars24.com/buy-used-bmw-x5-cars/"
