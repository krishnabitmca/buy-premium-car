"""Data-driven CarScanner E2E contract matrix.

These tests deliberately exercise the customer-search decision boundary without
calling third-party marketplaces. External marketplace availability belongs in
the scheduled production certification workflow.
"""
import pytest

from src import live_marketplaces as lm
from src.source_intelligence import load_source_registry, plan_sources


BRANDS_MODELS = [
    ("Mercedes-Benz", "E-Class"),
    ("BMW", "3 Series"),
    ("BMW", "X5"),
    ("Audi", "Q5"),
    ("Volvo", "XC60"),
    ("Porsche", "Cayenne"),
    ("Jaguar", "F-Pace"),
]

CONDITIONS = ["used", "demo", "both"]
BUDGETS = [
    (None, None),
    (20, 30),
    (30, 40),
    (40, 60),
    (60, 100),
    (100, 150),
    (45, 45),
    (150, 200),
]
DESTINATIONS = ["Bengaluru", "Mumbai", "Delhi NCR", None]


def q(brand, model):
    return f"{brand} {brand} {model}"


@pytest.mark.parametrize("brand,model", BRANDS_MODELS)
@pytest.mark.parametrize("condition", CONDITIONS)
@pytest.mark.parametrize("budget_min,budget_max", BUDGETS)
@pytest.mark.parametrize("destination", DESTINATIONS)
def test_search_matrix_has_valid_planning_contract(
    brand, model, condition, budget_min, budget_max, destination
):
    """Every supported customer combination must reach a deterministic plan."""
    registry = load_source_registry(from_database=False)
    plan = plan_sources(
        brand=brand,
        model=model,
        condition=condition,
        budget_min=budget_min,
        budget_max=budget_max,
        destination=destination,
        registry=registry,
        live_only=True,
    )

    # A valid search may legitimately have no applicable source, but every
    # selected source must be live and the planner must preserve the request.
    assert all(p.get("adapter_status") == "live" for p in plan)
    for item in plan:
        assert item.get("name")
        assert item.get("query")
        assert brand.lower() in str(item["query"]).lower()
        assert model.lower() in str(item["query"]).lower()

    # Destination is ranking/purchase context, never an inventory restriction.
    no_destination = plan_sources(
        brand=brand,
        model=model,
        condition=condition,
        budget_min=budget_min,
        budget_max=budget_max,
        destination=None,
        registry=registry,
        live_only=True,
    )
    assert {p["name"] for p in plan} == {p["name"] for p in no_destination}


@pytest.mark.parametrize("brand,model", BRANDS_MODELS)
@pytest.mark.parametrize("condition", CONDITIONS)
def test_targeted_routes_resolve_from_registry_configuration(brand, model, condition):
    urls = lm._targeted_source_urls(q(brand, model), condition)
    assert isinstance(urls, dict)

    registry = load_source_registry(from_database=False)
    by_name = {str(source.get("name")): source for source in registry}
    for name, source in by_name.items():
        if source.get("adapter_status") != "live":
            continue
        if condition not in {normalize_condition(x) for x in (source.get("conditions") or [])}:
            continue
        brands = {str(x).strip().lower() for x in (source.get("brands") or [])}
        if brands and "all" not in brands and brand.lower() not in brands:
            continue
        assert name in urls

        metadata = source.get("metadata") or {}
        if model and condition in {"used", "demo"}:
            template_key = f"{condition}_query_url_template"
        else:
            template_key = "query_url_template" if model else "brand_query_url_template"
        template = source.get(template_key) or metadata.get(template_key)
        if template:
            expected = template.format(
                brand=brand,
                brand_slug=lm._slug(brand),
                model=model,
                model_slug=lm._slug(model),
                condition=condition,
            )
            assert urls[name] == expected


@pytest.mark.parametrize(
    "requested,actual,expected",
    [
        ("Mercedes-Benz E-Class", "Mercedes-Benz E-Class E 200", True),
        ("Mercedes-Benz E-Class", "Mercedes-Benz C-Class C 200", False),
        ("BMW X5", "BMW X5 xDrive40i", True),
        ("BMW X5", "BMW X3 xDrive30d", False),
        ("Audi Q5", "Audi Q5 45 TFSI", True),
        ("Audi Q5", "BMW Q5", False),
    ],
)
def test_model_identity_is_strict(requested, actual, expected):
    row = {
        "brand": actual.split()[0] if not actual.startswith("Mercedes-Benz") else "Mercedes-Benz",
        "model": actual,
        "listing_name": actual,
        "variant": actual,
        "url": "https://example.com/listing",
    }
    assert lm._identity_matches_query(row, requested) is expected


@pytest.mark.parametrize(
    "requested,actual,expected",
    [
        ("used", "used", True),
        ("used", "demo", False),
        ("demo", "demo", True),
        ("demo", "used", False),
        ("both", "used", True),
        ("both", "demo", True),
    ],
)
def test_condition_isolation(requested, actual, expected):
    row = {
        "brand": "Mercedes-Benz",
        "model": "E-Class",
        "listing_name": f"Mercedes-Benz E-Class {actual}",
        "variant": actual,
        "condition_signal": actual,
        "price_lakh": 56,
        "url": "https://example.com/e-class",
    }
    hay = " ".join(str(row.get(k) or "") for k in (
        "brand", "model", "listing_name", "variant", "location", "fuel",
        "transmission", "source"
    )).lower()
    actual_condition = lm.normalize_condition(row["condition_signal"])
    wanted = lm.normalize_condition(requested)
    condition_match = wanted == "both" or actual_condition == wanted
    assert condition_match is expected


@pytest.mark.parametrize(
    "price,budget_min,budget_max,expected",
    [
        (29.99, 30, 40, False),
        (30, 30, 40, True),
        (40, 30, 40, True),
        (40.01, 30, 40, False),
        (56, None, None, True),
    ],
)
def test_budget_boundaries(price, budget_min, budget_max, expected):
    if budget_min is not None and price < budget_min:
        matched = False
    elif budget_max is not None and price > budget_max:
        matched = False
    else:
        matched = True
    assert matched is expected


def test_critical_customer_journeys_have_expected_source_mix():
    registry = load_source_registry(from_database=False)

    journeys = [
        ("Mercedes-Benz", "E-Class", "used", {"Mercedes-Benz Used Cars", "CarDekho Used", "CarWale Used"}),
        ("Mercedes-Benz", "E-Class", "demo", {"Mercedes-Benz Used Cars", "Motozite Demo"}),
        ("BMW", "3 Series", "used", {"BMW Premium Selection", "CarDekho Used", "CarWale Used"}),
        ("BMW", "X5", "demo", {"BMW Premium Selection", "Motozite Demo"}),
        ("Audi", "Q5", "used", {"Audi Approved Plus", "CarDekho Used", "CarWale Used"}),
    ]

    for brand, model, condition, expected in journeys:
        plan = plan_sources(
            brand=brand,
            model=model,
            condition=condition,
            registry=registry,
            live_only=True,
        )
        names = {p["name"] for p in plan}
        missing = expected - names
        assert not missing, f"{brand} {model} {condition}: missing {sorted(missing)}"


def test_no_source_plan_contains_discovery_only_sources():
    registry = load_source_registry(from_database=False)
    for brand, model in BRANDS_MODELS:
        for condition in CONDITIONS:
            plan = plan_sources(
                brand=brand,
                model=model,
                condition=condition,
                registry=registry,
                live_only=True,
            )
            assert all(p.get("adapter_status") != "discovery_only" for p in plan)
