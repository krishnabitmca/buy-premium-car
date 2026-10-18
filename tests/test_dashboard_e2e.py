import base64
import functools
import http.server
import threading
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api", reason="Playwright is required only for E2E tests")
sync_playwright = playwright.sync_playwright
expect = playwright.expect
pytestmark = pytest.mark.e2e


def buyer_routes(page):
    import json
    from src.search_intent import SearchIntent
    ids=['12345678-1234-1234-1234-123456789001','12345678-1234-1234-1234-123456789002']
    rows=[{'vehicle_id':identifier,'brand':'BMW','model':'X5','price_lakh':37+i*2,
           'price_basis':'unspecified','source':'Fixture Dealer','url':f'https://fixture.invalid/car/{i}',
           'fuel':'petrol','transmission':'automatic','body_type':'suv','km':20000,
           'mfg_year':2023,'condition_signal':'used','observed_at':'2026-10-18T17:00:00Z'}
          for i,identifier in enumerate(ids)]
    state={'rows':rows,'searches':[]}
    def catalog(route):
        payload={'ok':True,'mode':'live','models':[{'name':'X5'}]} if 'brand=' in route.request.url else {
                 'ok':True,'mode':'live','brands':[{'name':'BMW'},{'name':'Honda'}]}
        route.fulfill(content_type='application/json',body=json.dumps(payload))
    def intent(route):
        try:
            assert route.request.post_data_json['validate_only'] is True
            result={'ok':True,'model_used':False,'intent':SearchIntent.parse(route.request.post_data_json).public()}
            route.fulfill(content_type='application/json',body=json.dumps(result))
        except ValueError:
            route.fulfill(status=400,content_type='application/json',body='{"ok":false}')
    def search_result(route):
        state['searches'].append(route.request.post_data_json)
        route.fulfill(content_type='application/json',body=json.dumps({'ok':True,'mode':'inventory_partial',
            'search_scope':'india','availability_warning':'Fixture partial coverage','results':state['rows'],
            'sources':[{'name':'Fixture Dealer','status':'inventory','listings_found':len(state['rows'])}],
            'total_results':len(state['rows']),'has_more':False}))
    def shortlist(route):
        wanted=route.request.post_data_json['vehicle_ids']
        current=[row for row in state['rows'] if row['vehicle_id'] in wanted]
        route.fulfill(content_type='application/json',body=json.dumps({'ok':True,'results':current,
            'checked_at':'2026-10-18T18:00:00Z','unavailable_vehicle_ids':[]}))
    page.route('**/api/catalog*',catalog)
    page.route('**/api/intent',intent)
    page.route('**/api/search*',search_result)
    page.route('**/api/shortlist',shortlist)
    return state


def test_device_shortlist_comparison_rechecks_prices_and_sold_inventory(dashboard_url):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        state=buyer_routes(page)
        page.goto(dashboard_url,wait_until='networkidle')
        page.locator('#search').click();expect(page.locator('.card')).to_have_count(2)
        page.get_by_role('button',name='Save car on this device',exact=True).nth(0).click()
        page.get_by_role('button',name='Save car on this device',exact=True).nth(1).click()
        stored=page.evaluate("JSON.parse(localStorage.getItem('carscanner.buyer.v1'))")
        assert len(stored['cars'])==2 and all('price_lakh' not in row for row in stored['cars'])
        state['rows'][0]['price_lakh']=41
        page.locator('#savedChoices summary').click()
        expect(page.locator('#savedCars')).to_contain_text('₹41.00L')
        assert '₹37.00L' not in page.locator('#savedCars').inner_text()
        page.locator('.compareChoice').nth(0).check();page.locator('.compareChoice').nth(1).check()
        page.locator('#compareSaved').click()
        expect(page.locator('#modalTitle')).to_have_text('Compare saved cars')
        expect(page.locator('#modalBody')).to_contain_text('₹41.00L')
        page.keyboard.press('Escape');expect(page.locator('#compareSaved')).to_be_focused()
        state['rows']=state['rows'][1:]
        page.reload(wait_until='networkidle');page.locator('#savedChoices summary').click()
        expect(page.locator('#savedCars')).to_contain_text('Not currently revalidated')
        expect(page.locator('#buyerNotice')).to_contain_text('no longer eligible')
        assert '₹41.00L' not in page.locator('#savedCars').inner_text()
        page.context.set_offline(True)
        expect(page.locator('#connectionStatus')).to_be_visible()
        assert '₹39.00L' not in page.locator('#savedCars').inner_text()
        page.context.set_offline(False)
        expect(page.locator('#savedCars')).to_contain_text('₹39.00L')
        browser.close()


def test_share_search_restores_typed_intent_without_ai_or_seller_city_boundary(dashboard_url):
    import json
    from urllib.parse import urlsplit,parse_qs
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        buyer_routes(page);page.goto(dashboard_url,wait_until='networkidle')
        page.locator('#brand').select_option('BMW')
        expect(page.locator('#model')).to_be_enabled();page.locator('#model').select_option('X5')
        page.locator('#max').fill('40');page.locator('#destination').fill('Bengaluru')
        page.locator('#search').click();expect(page.locator('.card')).to_have_count(2)
        page.locator('#saveSearch').click()
        expect(page.locator('#savedSearches')).to_contain_text('BMW X5')
        page.locator('#shareSearch').click();expect(page.locator('#shareLink')).to_be_visible()
        link=page.locator('#shareLink').input_value()
        intent=json.loads(parse_qs(urlsplit(link).fragment)['search'][0])['intent']
        assert intent['query']=='BMW X5' and intent['budget_max']==40
        assert intent['destination']=='Bengaluru' and intent['seller_city']==''
        assert 'prompt' not in intent and 'consent' not in intent
        restored=browser.new_page();state=buyer_routes(restored)
        restored.goto(link,wait_until='networkidle')
        expect(restored.locator('.card')).to_have_count(2)
        assert restored.locator('#brand').input_value()=='BMW'
        assert restored.locator('#model').input_value()=='X5'
        assert state['searches'][-1]['destination']=='Bengaluru'
        assert state['searches'][-1]['seller_city']==''
        page.reload(wait_until='networkidle');expect(page.locator('#savedSearches')).to_contain_text('BMW X5')
        browser.close()


def test_invalid_shared_intent_does_not_execute_a_search(dashboard_url):
    import json
    from urllib.parse import urlencode
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();state=buyer_routes(page)
        fragment=urlencode({'search':json.dumps({'version':1,'intent':{'budget_max':-1}})})
        page.goto(dashboard_url+'#'+fragment,wait_until='networkidle')
        expect(page.locator('#buyerNotice')).to_contain_text('could not be restored')
        assert not state['searches']
        browser.close()
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


def test_clear_before_first_search_does_not_submit_broad_inventory_query(dashboard_url):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.route('**/api/catalog*',lambda route:route.fulfill(content_type='application/json',
            body='{"ok":true,"mode":"live","brands":[{"name":"BMW"}]}'))
        searches=[]
        page.route('**/api/search*',lambda route:(searches.append(route.request),route.abort()))
        page.goto(dashboard_url,wait_until='networkidle')
        page.locator('#brand').select_option('BMW')
        page.locator('#clear').click()
        page.wait_for_timeout(600)  # Exceeds the real 250ms automatic-search debounce.
        assert page.locator('#brand').input_value()==''
        assert not searches
        browser.close()


def test_old_model_response_cannot_replace_new_make(dashboard_url):
    import json
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        pending={}
        def catalog_route(route):
            url=route.request.url
            if 'brand=BMW' in url: pending['bmw']=route
            elif 'brand=Tata' in url:
                route.fulfill(content_type='application/json',body=json.dumps({'ok':True,'mode':'live','models':[{'name':'Nexon'}]}))
            else:
                route.fulfill(content_type='application/json',body=json.dumps({
                    'ok':True,'mode':'live','brands':[{'name':b} for b in ['BMW','Tata','Honda']]}))
        page.route('**/api/catalog*',catalog_route)
        page.goto(dashboard_url,wait_until='domcontentloaded')
        with page.expect_request('**/api/catalog?brand=BMW*'):
            page.locator('#brand').select_option('BMW')
        page.locator('#brand').select_option('Tata')
        page.locator('#model option',has_text='Nexon').wait_for(state='attached')
        pending['bmw'].fulfill(content_type='application/json',body=json.dumps({
            'ok':True,'mode':'live','models':[{'name':'X5'}]}))
        page.wait_for_load_state('networkidle')
        assert page.locator('#brand').input_value()=='Tata'
        assert page.locator('#model option').all_text_contents()==['All models','Nexon']
        assert page.locator('#model').is_enabled()
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
        browser=p.chromium.launch();page=browser.new_page();requests=[]
        page.route('**/api/catalog*',lambda route:route.fulfill(content_type='application/json',body=json.dumps({
            'ok':True,'mode':'live','brands':[{'name':'BMW'}],'models':[{'name':'X5'}]})))
        def search(route):
            body=route.request.post_data_json;requests.append(body)
            rows=[] if body.get('budget_max') and float(body['budget_max'])<79 else [{
                'brand':'BMW','model':'X5','price_lakh':79,'mfg_year':2024,'km':10000,
                'fuel':'Petrol','source':'Test dealer','url':'https://example.invalid/x5',
                'live_verified':True,'data_consistent':True,'condition_signal':'demo',
                'observed_at':'2026-10-10T08:00:00Z'}]
            route.fulfill(content_type='application/json',body=json.dumps({
                'ok':True,'mode':'inventory_partial','search_scope':'india','results':rows,
                'sources':[{'name':'Test dealer','status':'inventory','listings_found':len(rows)}]}))
        page.route('**/api/search*',search)
        from src.search_intent import SearchIntent
        interpreted=SearchIntent.parse({'query':'BMW X5','manufacture_year':2024,'budget_max':80}).public()
        page.route('**/api/intent',lambda route:route.fulfill(content_type='application/json',body=json.dumps({
            'ok':True,'intent':interpreted,'clarifications':[],'unverified_criteria':[]})))
        page.goto(dashboard_url);page.locator('#aiPrompt').fill('2024 BMW X5 under ₹80 lakh')
        page.locator('#askSearch').click();assert not requests
        assert 'Opt in' in page.locator('#aiReview').inner_text()
        page.locator('#aiConsent').check();page.locator('#askSearch').click()
        expect(page.locator('#applyIntent')).to_be_visible();assert not requests
        page.locator('#applyIntent').click();expect(page.locator('.card')).to_have_count(1)
        assert requests[-1]['query']=='BMW X5' and requests[-1]['budget_max']=='80'
        assert requests[-1]['manufacture_year']==2024
        page.get_by_role('button',name='Why this car?',exact=True).click()
        assert 'Stored marketplace observation' in page.locator('#modalBody').inner_text()
        assert 'Observation time' in page.locator('#modalBody').inner_text()
        assert 'Observed offers' in page.locator('#modalBody').inner_text()
        page.keyboard.press('Escape');expect(page.locator('#modal')).not_to_be_visible()
        page.locator('#fmax').fill('50');expect(page.locator('.card')).to_have_count(0)
        assert not page.locator('#market').is_visible()
        page.locator('#clear').click();expect(page.locator('.card')).to_have_count(1)
        assert page.locator('#brand').input_value()=='' and page.locator('#max').input_value()==''
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


def test_empty_brand_search_exposes_and_clears_refinements(dashboard_url):
    import json
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();requests=[]
        page.route('**/api/catalog*',lambda r:r.fulfill(content_type='application/json',body=json.dumps({
            'ok':True,'mode':'live','brands':[{'name':'Honda'}],'models':[{'name':'City'}]})))
        def respond(r):
            body=r.request.post_data_json;requests.append(body)
            rows=[] if body.get('body_types') else [{'brand':'Honda','model':'City','fuel':'Petrol','price_lakh':8,'condition_signal':'used','source':'Fixture','url':'https://example.invalid/honda'}]
            r.fulfill(content_type='application/json',body=json.dumps({'ok':True,'mode':'inventory_partial','search_scope':'india','results':rows,'total_results':len(rows),'sources':[]}))
        page.route('**/api/search*',respond)
        page.goto(dashboard_url);page.locator('#brand').select_option('Honda')
        page.locator('#condition').select_option('used');page.locator('#bodyType').select_option('suv')
        page.locator('#search').click();expect(page.locator('#activeCriteria')).to_contain_text('suv')
        expect(page.locator('.card')).to_have_count(0)
        page.get_by_role('button',name='Search this brand without refinements',exact=True).click()
        expect(page.locator('.card')).to_have_count(1)
        assert requests[-1]['query']=='Honda' and requests[-1]['condition']=='used'
        assert requests[-1]['body_types']==[] and page.locator('#bodyType').input_value()==''
        browser.close()
