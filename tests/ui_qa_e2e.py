import asyncio
from playwright.async_api import async_playwright

RESULT = {
    "ok": True, "mode": "live", "live_at": "2026-10-01T08:00:00Z",
    "sources": [
        {"source":"CarDekho Used","status":"live","listings_found":3},
        {"source":"CarWale Used","status":"live","listings_found":1},
        {"source":"Cars24 Luxury Used","status":"unavailable","listings_found":0}
    ],
    "results": [
        {"brand":"BMW","model":"X5","variant":"xDrive40i","price_lakh":49.5,"mfg_year":2024,"km":18000,"fuel":"Petrol","transmission":"Automatic","location":"Delhi","source":"CarDekho Used","url":"https://example.com/bmw-x5","live_verified":True,"data_consistent":True,"discount_pct":5.2,"comp_median":52.2,"source_count":2},
        {"brand":"BMW","model":"X5","variant":"xDrive30d","price_lakh":55.0,"mfg_year":2023,"km":42000,"fuel":"Diesel","transmission":"Automatic","location":"Bengaluru","source":"CarWale Used","url":"https://example.com/bmw-x5-2","live_verified":True,"data_consistent":True,"discount_pct":-5.3,"comp_median":52.2,"source_count":1},
        {"brand":"Audi","model":"Q5","variant":"Technology","price_lakh":44.0,"mfg_year":2025,"km":8000,"fuel":"Petrol","transmission":"Automatic","location":"Mumbai","source":"CarDekho Used","url":"https://example.com/audi-q5","live_verified":True,"data_consistent":True,"discount_pct":None,"comp_median":None,"source_count":1}
    ]
}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors=[]
        page.on("console", lambda msg: errors.append(msg.text) if msg.type=="error" else None)
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        async def route(route):
            u=route.request.url
            if "/api/catalog" in u:
                if "brand=" in u:
                    await route.fulfill(status=200,content_type="application/json",
                        body='{"ok":true,"mode":"live","models":[{"name":"X5"},{"name":"X3"}]}')
                else:
                    await route.fulfill(status=200,content_type="application/json",
                        body='{"ok":true,"mode":"live","brands":[{"name":"BMW"},{"name":"Audi"}]}')
            elif "/api/search" in u:
                await route.fulfill(status=200,content_type="application/json",body=__import__("json").dumps(RESULT))
            else:
                await route.continue_()

        await page.route("**/api/**",route)
        await page.goto("http://127.0.0.1:4173/index.html")
        await page.wait_for_load_state("domcontentloaded")

        # Discovery and dependent catalogue.
        assert await page.locator("#brand").is_visible()
        await page.locator("#brand").select_option(label="BMW")
        await page.locator("#model").wait_for()
        assert await page.locator("#model option").count() == 3

        # Core E2E search.
        await page.locator("#max").fill("55")
        await page.locator("#destination").fill("Bengaluru")
        await page.locator("#search").click()
        await page.locator(".card").first.wait_for()
        assert await page.locator(".card").count() == 3
        assert "LIVE" in await page.locator(".livebar").inner_text()
        assert "Bengaluru" in await page.locator("#destination").input_value()

        # Seller-city filtering must work after live search.
        await page.locator("#city").select_option(label="Delhi")
        assert await page.locator(".card").count() == 1
        assert "Delhi" in await page.locator(".card").inner_text()

        # Price filtering must work.
        await page.locator("#city").select_option(label="")
        await page.locator("#fmax").fill("50")
        await page.locator("#fmax").press("Enter")
        assert await page.locator(".card").count() == 2

        # Fuel filter.
        await page.locator("#fmax").fill("")
        await page.locator(".fuelCheck[value=diesel]").check()
        assert await page.locator(".card").count() == 1
        assert "Diesel" in await page.locator(".card").inner_text()

        # Clear all.
        await page.locator("#clear").click()
        assert await page.locator(".card").count() == 3
        assert await page.locator("#destination").input_value() == "Bengaluru"

        # Sort lowest price.
        await page.locator("#sort").select_option("price")
        prices=await page.locator(".card .price").all_inner_texts()
        assert prices[0] == "₹44.00L"

        # Natural language search.
        await page.locator("#aiPrompt").fill("BMW X5 under ₹55 lakh")
        await page.locator("#askSearch").click()
        await page.locator(".card").first.wait_for()
        assert await page.locator("#max").input_value() == "55"

        # Market intelligence and evidence modal.
        assert await page.locator("#market").is_visible()
        assert "comparable" in (await page.locator("#marketNote").inner_text()).lower()
        await page.locator("button.secondary").first.click()
        assert await page.locator("#modal").is_visible()
        assert "Live marketplace observation" in await page.locator("#modalBody").inner_text()
        await page.locator(".close").click()

        # Original listing link must remain a direct external link.
        href=await page.locator(".card a.primary").first.get_attribute("href")
        assert href.startswith("https://example.com/")

        # Adversarial: no matching filter must produce a clean empty state.
        await page.locator("#fmin").fill("100")
        await page.locator("#fmax").fill("120")
        await page.locator("#clear").click()
        await page.locator("#fmin").fill("100")
        await page.locator("#search").click()
        # The mocked response ignores request budget, so use seller-city impossible value instead.
        await page.locator("#city").select_option(label="")
        await page.locator("#fmin").fill("100")
        await page.locator("#fmax").fill("120")
        await page.locator("#sort").select_option("price")
        # applyResults is driven by change; force a known filter event.
        await page.locator("#fmax").dispatch_event("change")
        assert await page.locator(".empty").count() >= 1

        if errors:
            raise AssertionError("Browser console/page errors: "+repr(errors))
        print("PASS: adversarial browser E2E suite")
        await browser.close()

asyncio.run(main())
