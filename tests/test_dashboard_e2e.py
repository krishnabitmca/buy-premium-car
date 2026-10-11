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


def test_partial_inventory_loads_more_without_losing_search(dashboard_url):
    import json
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.route('**/api/catalog*',lambda route:route.fulfill(status=200,content_type='application/json',body='{"ok":true,"mode":"live","brands":[]}'))
        requests=[]
        def respond(route):
            body=route.request.post_data_json;requests.append(body)
            number=body['page']
            payload={'ok':True,'mode':'inventory_partial','search_scope':'india','inventory_total':2,'total_results':2,'has_more':number==1,
                'sources':[{'name':'Source '+str(number),'status':'inventory','listings_found':1}],
                'results':[{'brand':'BMW','model':'X1','price_lakh':30+number,'source':'Source '+str(number),'url':'https://example.com/car/'+str(number),'condition_signal':'used'}]}
            route.fulfill(status=200,content_type='application/json',body=json.dumps(payload))
        page.route('**/api/search*',respond)
        page.goto(dashboard_url);page.locator('#search').click()
        page.locator('#more').wait_for(state='visible')
        assert page.locator('.card').count()==1
        page.locator('#more').click()
        page.wait_for_function("document.querySelectorAll('.card').length===2")
        assert not page.locator('#more').is_visible()
        assert [r['page'] for r in requests]==[1,2]
        assert requests[0]['query']==requests[1]['query']
        assert '2 of 2' in page.locator('#meta').inner_text()
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


def test_stored_inventory_assistant_and_filters_are_honest(dashboard_url):
    import json
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.route('**/api/catalog*',lambda route:route.fulfill(content_type='application/json',body=json.dumps({
            'ok':True,'mode':'live','brands':[{'name':'BMW'}],'models':[{'name':'X5'}]})))
        requests=[]
        def search(route):
            requests.append(route.request.post_data_json)
            route.fulfill(content_type='application/json',body=json.dumps({
                'ok':True,'mode':'inventory_partial','search_scope':'india',
                'sources':[{'name':'Test dealer','status':'inventory','listings_found':1}],
                'results':[{'brand':'BMW','model':'X5 xDrive40i','price_lakh':79,
                    'mfg_year':2024,'km':10000,'fuel':'Petrol','source':'Test dealer',
                    'url':'https://example.invalid/x5','live_verified':True,
                    'data_consistent':True,'condition_signal':'demo',
                    'observed_at':'2026-10-10T08:00:00Z'}]}))
        page.route('**/api/search*',search)
        page.goto(dashboard_url)
        page.locator('#aiPrompt').fill('2024 BMW X5 under ₹80 lakh')
        page.locator('#askSearch').click()
        page.locator('.card').wait_for()
        assert requests[-1]['query']=='BMW X5'
        assert requests[-1]['budget_min'] is None
        assert requests[-1]['budget_max']=='80'
        assert '1 source(s) with matches' in page.locator('#summary').inner_text()
        page.locator('.secondary').click()
        assert 'Stored marketplace observation' in page.locator('#modalBody').inner_text()
        assert 'Observation time' in page.locator('#modalBody').inner_text()
        page.locator('.close').click()
        page.locator('#fmax').fill('50')
        assert page.locator('.card').count()==0
        assert not page.locator('#market').is_visible()
        page.locator('#clear').click()
        assert page.locator('#brand').input_value()==''
        assert page.locator('#max').input_value()==''
        assert page.locator('.card').count()==1
        browser.close()


def test_empty_demo_search_distinguishes_fetched_sources_from_matches(dashboard_url):
    import json
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("**/api/catalog*", lambda route: route.fulfill(
            content_type="application/json", body=json.dumps({
                "ok": True, "mode": "live", "brands": [{"name": "BMW"}],
                "models": [{"name": "X1"}],
            })))
        requests = []
        def search(route):
            requests.append(route.request.post_data_json)
            route.fulfill(content_type="application/json", body=json.dumps({
                "ok": True, "mode": "live", "search_scope": "india",
                "sources": [{"source": "Motozite Demo", "status": "live", "listings_found": 0}],
                "results": [],
            }))
        page.route("**/api/search*", search)
        page.goto(dashboard_url)
        page.locator("#brand").select_option("BMW")
        page.locator("#model").select_option("X1")
        page.locator("#condition").select_option("demo")
        page.locator("#search").click()
        page.get_by_text("No verified matching listings returned.").wait_for()
        assert page.locator(".card").count() == 0
        assert "1 source(s) fetched · 0 source(s) with matches" in page.locator("#summary").inner_text()
        assert "does not establish that no cars are available" in page.locator("#grid").inner_text()
        assert requests[0]["query"] == "BMW X1"
        assert requests[0]["condition"] == "demo"
        browser.close()
