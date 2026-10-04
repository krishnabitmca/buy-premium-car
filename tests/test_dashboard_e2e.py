import base64
import functools
import http.server
import threading
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api", reason="Playwright is required only for E2E tests")
sync_playwright = playwright.sync_playwright
pytestmark = pytest.mark.e2e
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/6fX0VQAAAABJRU5ErkJggg==")

@pytest.fixture(scope="module")
def dashboard_url():
    root = Path(__file__).resolve().parents[1]
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    finally:
        server.shutdown()
        thread.join(timeout=3)

def test_current_search_first_journey(dashboard_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors=[]
        page.on("pageerror", lambda e: errors.append(str(e)))
        async_catalog = '{"ok":true,"mode":"live","brands":[{"name":"BMW"},{"name":"Audi"}]}'
        page.route("**/api/catalog*", lambda route: route.fulfill(status=200,content_type="application/json",body=async_catalog))
        page.goto(dashboard_url, wait_until="domcontentloaded")
        assert page.title() == "CarScanner — Compare every marketplace"
        assert page.locator("#brand").count() == 1
        assert page.locator("#model").count() == 1
        assert page.locator("#condition").count() == 1
        assert page.locator("#destination").input_value() == ""
        assert page.locator(".hero h1").inner_text() == "Find the right car at the right price"
        assert page.locator(".card").count() == 0
        assert not errors
        browser.close()

def test_mobile_layout_and_filters_are_present(dashboard_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width":390,"height":844})
        page.goto(dashboard_url, wait_until="domcontentloaded")
        assert page.locator(".hero").count() == 1
        assert page.locator("#destination").count() == 1
        assert page.locator("#clear").count() == 1
        assert page.locator(".chip").count() >= 6
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        browser.close()

def test_current_evidence_action_is_wired(dashboard_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("**/api/catalog*", lambda route: route.fulfill(status=200,content_type="application/json",body='{"ok":true,"mode":"live","brands":[{"name":"BMW"}]}'))
        page.route("**/api/search*", lambda route: route.fulfill(status=200,content_type="application/json",body='{"ok":true,"mode":"live","search_scope":"india","live_at":"2026-10-01T08:00:00Z","sources":[{"source":"Test","status":"live"}],"results":[{"brand":"BMW","model":"X5","variant":"xDrive40i","price_lakh":49.5,"mfg_year":2024,"km":18000,"fuel":"Petrol","transmission":"Automatic","location":"Delhi","source":"Test","url":"https://example.com/x5","live_verified":true,"data_consistent":true,"condition_signal":"used"}]}'))
        page.goto(dashboard_url, wait_until="domcontentloaded")
        page.locator("#search").click()
        page.locator(".card").first.wait_for()
        page.locator(".card button.secondary").first.click()
        assert page.locator("#modal.show").count() == 1
        assert "Live marketplace observation" in page.locator("#modalBody").inner_text()
        browser.close()
