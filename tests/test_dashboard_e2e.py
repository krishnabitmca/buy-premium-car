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


def test_buyer_discovery_filter_and_evidence_flow(dashboard_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})

        def route_images(route):
            if route.request.resource_type == "image":
                route.fulfill(status=200, content_type="image/png", body=PNG)
            else:
                route.continue_()

        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.route("**/*", route_images)
        page.goto(dashboard_url, wait_until="networkidle")

        assert not page_errors, "Dashboard JavaScript error: " + " | ".join(page_errors)
        assert page.title() == "Used & Demo Car Deal Radar"
        assert page.locator(".card").count() == 3
        assert page.locator(".photo img").count() >= 2
        assert page.locator("#resultCount").inner_text().startswith("3 result")

        page.locator("#q").fill("Audi Q3")
        assert page.locator(".card").count() == 1
        assert "Audi Q3" in page.locator(".card").inner_text()

        page.locator(".secondary").first.click()
        assert page.locator("#modal.show").count() == 1
        assert page.locator("#mTitle").inner_text() == "Audi Q3"
        assert page.locator(".modal-grid .kv").count() >= 9
        page.locator(".close").click()
        assert page.locator("#modal.show").count() == 0
        browser.close()


def test_mobile_layout_has_no_horizontal_overflow(dashboard_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(dashboard_url, wait_until="networkidle")
        assert page.locator(".card").count() == 3
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.locator(".grid").evaluate("(el) => getComputedStyle(el).gridTemplateColumns").count(" ") == 0
        browser.close()
