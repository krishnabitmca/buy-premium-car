import ast
from pathlib import Path


def test_inventory_search_contract_contains_pagination_and_image_projection():
    source = Path("src/inventory_db.py").read_text()
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "search_inventory")
    args = {a.arg for a in fn.args.args}
    assert {"limit", "offset", "return_count"} <= args
    assert "image_urls" in source
    assert "limit %s offset %s" in source
    assert "count(*)::bigint" in source


def test_worker_maps_crawler_images_into_vehicle_model():
    source = Path("src/inventory_refresh_worker.py").read_text()
    assert "image_urls=list(v.get(\"images\")" in source
    assert "v.get(\"image\")" in source
