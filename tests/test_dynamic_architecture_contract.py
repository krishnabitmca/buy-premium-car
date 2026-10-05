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
    assert "load_source_registry" in source or "live_brands" in source
    assert "['BMW'" not in source
    assert "['Audi'" not in source
    assert "Maruti Suzuki" not in source


def test_catalog_brand_resolution_requires_database_or_explicit_configuration():
    source = Path("src/live_marketplaces.py").read_text()
    assert 'CARSCANNER_CATALOG_BRANDS_JSON' in source
    assert 'load_source_registry' in source
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


def test_catalog_brand_discovery_is_source_driven(monkeypatch):
    import src.live_marketplaces as lm

    monkeypatch.delenv("CARSCANNER_CATALOG_BRANDS_JSON", raising=False)
    monkeypatch.delenv("CARSCANNER_CATALOG_SOURCE_URL", raising=False)
    monkeypatch.setattr(lm, "_registry_brand_records", lambda: [])
    monkeypatch.setattr(lm, "load_source_registry", lambda: [
        {"name": "Configured Catalog", "catalog_url": "https://catalog.example/newcars", "catalog_exclude_paths": ["compare-cars", "electric-cars", "new-cars", "used-cars", "demo-cars"]}
    ])
    monkeypatch.setattr(
        lm,
        "fetch_text",
        lambda url: """
        <a href="/cars/BMW">BMW</a>\n        <a href="/compare-cars">Compare</a>\n        <a href="/electric-cars">Electric</a>
        <a href="/cars/Audi">Audi</a>
        <a href="/cars/BMW/X5">X5</a>
        <a href="/new-cars">New Cars</a>
        """,
    )

    brands = lm.live_brands()
    assert [x["name"] for x in brands] == ["Audi", "BMW"]
    assert all(x["catalog_verified"] == "discovered" for x in brands)

def test_source_route_resolution_is_registry_driven():
    from src import live_marketplaces as lm

    source = Path("src/live_marketplaces.py").read_text()
    start = source.index("def _targeted_source_urls")
    end = source.index("def _canonical_url", start)
    resolver = source[start:end].lower()

    for token in ("cardekho.com", "carwale.com", "cars24.com", "spinny.com", "motozite.com"):
        assert token not in resolver

    assert "load_source_registry()" in resolver
    assert "query_url_template" in resolver


def test_registry_contains_query_route_configuration_for_primary_marketplaces():
    import yaml

    data = yaml.safe_load(Path("config/sources.yaml").read_text())
    sources = {x["name"]: x for x in data["known_sources"]}
    for name in ("CarDekho Used", "CarWale Used", "Cars24 Luxury Used", "Spinny Luxury Used"):
        assert sources[name].get("query_url_template")


def test_catalog_brand_resolution_uses_configured_route_when_label_join_misses(monkeypatch):
    import src.live_marketplaces as lm

    monkeypatch.delenv("CARSCANNER_CATALOG_BRANDS_JSON", raising=False)
    monkeypatch.delenv("CARSCANNER_CATALOG_SOURCE_URL", raising=False)
    monkeypatch.setattr(lm, "_registry_brand_records", lambda: [
        {"name": "BMW", "slug": "bmw", "url": "", "catalog_verified": "database"},
        {"name": "Mercedes-Benz", "slug": "mercedes-benz", "url": "", "catalog_verified": "database"},
    ])
    monkeypatch.setattr(lm, "load_source_registry", lambda: [
        {
            "name": "Configured Catalog",
            "catalog_url": "https://catalog.example/newcars",
            "catalog_brand_url_template": "https://catalog.example/{brand_slug}-cars",
        }
    ])
    monkeypatch.setattr(lm, "fetch_text", lambda url: "<a href='/bmw/x5'>BMW X5</a><a href='/bmw/3-series'>BMW 3 Series</a>")

    brands = lm.live_brands()
    urls = {x["name"]: x["url"] for x in brands}
    assert urls["BMW"] == "https://catalog.example/bmw-cars"
    assert urls["Mercedes-Benz"] == "https://catalog.example/mercedes-benz-cars"


def test_catalog_brand_resolution_identity_matches_changed_anchor_labels(monkeypatch):
    import src.live_marketplaces as lm

    monkeypatch.delenv("CARSCANNER_CATALOG_BRANDS_JSON", raising=False)
    monkeypatch.delenv("CARSCANNER_CATALOG_SOURCE_URL", raising=False)
    monkeypatch.setattr(lm, "_registry_brand_records", lambda: [
        {"name": "Mercedes-Benz", "slug": "mercedes-benz", "url": "", "catalog_verified": "database"},
    ])
    monkeypatch.setattr(lm, "load_source_registry", lambda: [
        {"name": "Configured Catalog", "catalog_url": "https://catalog.example/newcars"}
    ])
    monkeypatch.setattr(
        lm,
        "fetch_text",
        lambda url: "<a href='/cars/mercedes-benz'>Mercedes Benz Cars</a>"
    )

    brands = lm.live_brands()
    assert brands[0]["url"] == "https://catalog.example/cars/mercedes-benz"


def test_live_models_accepts_models_from_configured_catalog_host(monkeypatch):
    import src.live_marketplaces as lm

    monkeypatch.delenv("CARSCANNER_CATALOG_BRANDS_JSON", raising=False)
    monkeypatch.delenv("CARSCANNER_CATALOG_SOURCE_URL", raising=False)
    monkeypatch.setattr(lm, "_registry_brand_records", lambda: [
        {"name": "BMW", "slug": "bmw", "url": "", "catalog_verified": "database"},
    ])
    monkeypatch.setattr(lm, "load_source_registry", lambda: [
        {
            "name": "Configured Catalog",
            "catalog_url": "https://catalog.example/newcars",
            "catalog_brand_url_template": "https://catalog.example/{brand_slug}-cars",
        }
    ])
    def fake_fetch(url):
        if url == "https://catalog.example/newcars":
            return "<a href='/not-the-same-label'>BMW Cars</a>"
        return """
            <a href='/bmw/x5'>BMW X5</a>
            <a href='/bmw/3-series'>BMW 3 Series</a>
            <a href='/bmw/gallery'>Gallery</a>
            <a href='/bmw/x5/offers'>Offers</a>
        """
    monkeypatch.setattr(lm, "fetch_text", fake_fetch)

    models = lm.live_models("BMW")
    assert [x["name"] for x in models] == ["3 Series", "X5"]
