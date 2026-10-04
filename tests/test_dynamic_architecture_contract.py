from pathlib import Path


def test_customer_catalog_has_no_baked_in_business_taxonomy():
    html = Path("index.html").read_text()
    marketplace = Path("src/live_marketplaces.py").read_text()

    forbidden = [
        "FALLBACK_BRANDS",
        "CURRENT_BRANDS",
        "MODEL_FALLBACKS",
        "value=\"Bengaluru\"",
        "destination').value='Bengaluru'",
    ]
    combined = html + "\n" + marketplace
    for token in forbidden:
        assert token not in combined, f"customer taxonomy must be DB/config driven: {token}"


def test_catalog_endpoint_is_not_the_source_of_baked_in_brand_lists():
    source = Path("api/catalog.py").read_text()
    assert "load_registry" in source or "live_brands" in source
    assert "['BMW'" not in source
    assert "['Audi'" not in source
    assert "Maruti Suzuki" not in source


def test_catalog_brand_resolution_requires_database_or_explicit_configuration():
    source = Path("src/live_marketplaces.py").read_text()
    assert 'CARSCANNER_CATALOG_BRANDS_JSON' in source
    assert 'load_registry' in source
    assert 'CARSCANNER_CATALOG_SOURCE_URL' in source
    assert 'CARSCANNER_MODEL_CATALOG_URL_TEMPLATE' in source


def test_runtime_dependency_declares_psycopg_for_database_driven_paths():
    source = Path("pyproject.toml").read_text()
    assert '"psycopg[binary]>=3.2,<4"' in source


def test_vercel_runtime_requirements_include_database_driver():
    source = Path("api/requirements.txt").read_text()
    assert "psycopg[binary]>=3.2,<4" in source


def test_removed_catalog_fallback_symbols_do_not_reappear():
    source = Path("src/live_marketplaces.py").read_text()
    assert "_fallback_models" not in source
    assert "CURRENT_BRANDS" not in source
    assert "MODEL_FALLBACKS" not in source
