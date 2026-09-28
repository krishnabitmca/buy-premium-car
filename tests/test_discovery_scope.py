from src.discovery import build_query_bank

def test_discovery_is_india_wide_and_not_city_whitelisted():
    queries=build_query_bank({
        "brands":["Hyundai","BMW"],
        "all_india":True,
        "city_hints":["Bengaluru","Jaipur","Kochi"],
        "city_hints_per_run":2,
        "queries_per_brand":2,
    })
    assert '"Hyundai" "used car" India' in queries
    assert '"BMW" "demo car" India' in queries
    assert '"Hyundai" "used car" "Bengaluru"' in queries
    assert '"BMW" "demo car" "Jaipur"' in queries


def test_city_discovery_is_not_multiplied_by_brand_count():
    queries=build_query_bank({
        "brands":["Hyundai","BMW","Audi"],
        "all_india":True,
        "city_hints":["Bengaluru","Jaipur","Kochi"],
        "city_hints_per_run":2,
        "queries_per_brand":2,
    })
    # 3 brands x 2 nationwide queries + 2 cities x 2 generic local queries.
    assert len(queries)==10
