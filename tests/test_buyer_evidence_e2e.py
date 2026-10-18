import json
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright,expect
from test_dashboard_e2e import dashboard_url,buyer_routes
pytestmark=pytest.mark.e2e


def open_car(page,dashboard_url):
    buyer_routes(page)
    page.goto(dashboard_url,wait_until='networkidle');page.locator('#search').click()
    expect(page.locator('.card')).to_have_count(2)
    page.get_by_role('button',name='Why this car?',exact=True).nth(0).click()
    return page.locator('#buyerEvidence')


def test_ai_evidence_consent_sources_and_no_html_execution(dashboard_url):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();calls=[]
        def explain(route):
            calls.append(route.request.post_data_json)
            route.fulfill(content_type='application/json',body=json.dumps({'ok':True,
                'abstained':False,'checked_at':'2026-10-18T12:00:00Z',
                'facts':[{'id':'s1.price','text':'Recorded asking price: INR 37.00 lakh. <script>throw Error("untrusted")</script>',
                    'source_ids':['s1'],'observed_at':'2026-10-18T12:00:00Z'}],
                'sources':[{'id':'s1','name':'Original dealer','url':'https://seller.invalid/car/1'}],
                'unknowns':['Inspection and warranty are not established.']}))
        page.route('**/api/explain',explain)
        guide=open_car(page,dashboard_url)
        guide.get_by_label('Question about this car').fill('What evidence supports its price?')
        guide.get_by_role('button',name='Select evidence with AI').click()
        expect(guide).to_contain_text('Opt in before sending')
        assert calls==[]
        guide.locator('input[type="checkbox"]').check()
        guide.get_by_role('button',name='Select evidence with AI').click()
        expect(guide).to_contain_text('INR 37.00 lakh')
        expect(guide).to_contain_text('<script>')
        assert guide.locator('script').count()==0
        assert guide.get_by_role('link',name='Original dealer ↗').get_attribute('href')=='https://seller.invalid/car/1'
        assert set(calls[0])=={'vehicle_id','price_basis','question','consent'}
        assert calls[0]['consent'] is True
        page.keyboard.press('Escape');expect(page.locator('#modal')).not_to_have_class('modal show')
        browser.close()


def test_ai_failure_keeps_original_dossier_and_allows_retry_without_auto_replay(dashboard_url):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();calls=[]
        def unavailable(route):
            calls.append(1);route.fulfill(status=503,content_type='application/json',body='{"ok":false,"error":"AI testing limit reached. Read original offers."}')
        page.route('**/api/explain',unavailable)
        guide=open_car(page,dashboard_url)
        guide.get_by_label('Question about this car').fill('Is warranty established?')
        guide.locator('input[type="checkbox"]').check()
        guide.get_by_role('button',name='Select evidence with AI').click()
        expect(guide).to_contain_text('AI testing limit reached')
        expect(guide.get_by_role('button',name='Select evidence with AI')).to_be_enabled()
        assert calls==[1]
        expect(page.locator('#modalBody')).to_contain_text('Asking price')
        browser.close()
