import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        async def route_handler(route):
            url = route.request.url
            if "/api/catalog" in url:
                if "brand=" in url:
                    await route.fulfill(status=200, content_type="application/json",
                        body='{"ok":true,"mode":"live","models":[{"name":"X5"}]}')
                else:
                    await route.fulfill(status=200, content_type="application/json",
                        body='{"ok":true,"mode":"live","brands":[{"name":"BMW"}]}')
            elif "/api/search" in url:
                await route.fulfill(status=200, content_type="application/json", body='''{
                    "ok":true,"mode":"live","search_scope":"india","live_at":"2026-09-29T08:00:00Z",
                    "sources":[{"source":"Fixture","status":"live","listings_found":1}],
                    "results":[{
                      "brand":"BMW","model":"X5","variant":"xDrive40i M Sport",
                      "price_lakh":49.5,"mfg_year":2024,"km":18000,
                      "fuel":"Petrol","transmission":"Automatic","location":"Delhi",
                      "source":"Fixture","url":"https://example.com/bmw-x5","images":["https://example.com/images/bmw-x5.jpg"],
                      "live_verified":true,"data_consistent":true,
                      "discount_pct":5.2,"comp_median":52.2,"source_count":1
                    }]
                }''')
            else:
                await route.continue_()

        await page.route("**/api/**", route_handler)
        await page.goto("http://127.0.0.1:4173/index.html")
        await page.wait_for_load_state("domcontentloaded")

        assert await page.locator("h1").inner_text() == "Find the right car at the right price"
        assert await page.locator("#brand").is_visible()
        assert await page.locator("#model").is_visible()

        await page.locator("#brand").select_option(label="BMW")
        await page.wait_for_timeout(100)
        await page.locator("#search").click()
        await page.locator(".card").wait_for()

        assert "BMW X5" in await page.locator(".card .title").inner_text()
        assert "₹49.50L" in await page.locator(".card .price").inner_text()
        assert "LIVE" in await page.locator(".livebar").inner_text()

        if errors:
            raise AssertionError("Browser console/page errors: " + repr(errors))

        print("PASS: browser smoke test")
        await browser.close()

asyncio.run(main())
