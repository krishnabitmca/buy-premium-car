"""Real Chromium service-worker/offline test; no offline inventory is fabricated."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright,expect
from test_dashboard_e2e import dashboard_url,buyer_routes
pytestmark=pytest.mark.e2e


def test_cold_offline_shell_retains_choices_without_caching_inventory(dashboard_url):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        state=buyer_routes(page)
        page.goto(dashboard_url,wait_until='networkidle')
        page.evaluate('navigator.serviceWorker.ready')
        page.wait_for_function('navigator.serviceWorker.controller!==null')
        page.locator('#search').click();expect(page.locator('.card')).to_have_count(2)
        page.locator('#saveSearch').click()
        expect(page.locator('#savedSearches')).to_contain_text('All India cars')
        requests=page.evaluate('''async()=>{
            const keys=await caches.keys(),urls=[];
            for(const key of keys)for(const request of await (await caches.open(key)).keys())urls.push(new URL(request.url).pathname);
            return urls;
        }''')
        assert '/index.html' in requests and '/buyer_state.js' in requests
        assert not any(path.startswith('/api/') for path in requests)
        page.context.set_offline(True)
        page.reload(wait_until='domcontentloaded')
        expect(page.locator('#connectionStatus')).to_be_visible()
        expect(page.locator('#savedSearches')).to_contain_text('All India cars')
        assert page.locator('.card').count()==0
        page.context.set_offline(False)
        state['rows'][0]['price_lakh']=43
        page.locator('#search').click()
        expect(page.locator('.card')).to_have_count(2)
        expect(page.locator('#grid')).to_contain_text('₹43.00L')
        browser.close()
