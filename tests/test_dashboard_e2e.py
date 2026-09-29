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


def test_carcanner_search_first_journey(dashboard_url):
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
        assert page.title() == "Carcanner — Search Used & Demo Cars in India"
        assert page.locator(".search-hero").count() == 1
        assert page.locator("#q").count() == 1
        assert page.locator("#destination").input_value() == "Bengaluru"
        assert page.locator("#budgetMin").count() == 1
        assert page.locator("#budgetMax").count() == 1
        assert page.locator("#searchCars").count() == 1
        assert "all india" in page.locator(".scope").inner_text().lower()
        assert page.locator(".card").count() == 3

        page.locator("#q").fill("Audi Q3")
        page.locator("#budgetMin").fill("30")
        page.locator("#budgetMax").fill("40")
        page.locator("#searchCars").click()
        assert page.locator(".card").count() == 1
        assert "Audi Q3" in page.locator(".card").inner_text()
        assert "India" in page.locator(".summary-right").inner_text()

        page.locator("#moreFilters").click()
        assert page.locator("#advanced.show").count() == 1
        for selector in ["#maxAge", "#mileage", "#owners", "#fuel", "#transmission", "#condition", "#certification", "#deal", "#clearFilters"]:
            assert page.locator(selector).count() == 1
        page.locator("#moreFilters").click()
        assert page.locator("#advanced.show").count() == 0

        browser.close()


def test_compare_and_inspect(dashboard_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(dashboard_url, wait_until="networkidle")

        compare_buttons = page.locator("[data-compare]")
        assert compare_buttons.count() == 3
        compare_buttons.nth(0).click()
        compare_buttons.nth(1).click()
        assert page.locator("#compareTray.show").count() == 1

        page.locator("#compareOpen").click()
        assert page.locator("#compareModal.show").count() == 1
        assert page.locator(".compare-table").count() == 1
        page.locator("#compareModal .close").click()

        page.locator("[data-inspect]").first.click()
        assert page.locator("#inspectModal.show").count() == 1
        assert page.locator("#inspectTitle").inner_text()
        assert page.locator("#inspectBody .inspect-card").count() >= 2

        browser.close()


def test_mobile_layout_has_no_horizontal_overflow(dashboard_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(dashboard_url, wait_until="networkidle")
        assert page.locator(".search-hero").count() == 1
        assert page.locator(".card").count() == 3
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        browser.close()
