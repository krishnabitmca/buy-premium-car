import asyncio
import json
from playwright.async_api import async_playwright

RESULT = {
    "ok": True,
    "mode": "live",
    "live_at": "2026-10-01T08:00:00Z",
    "sources": [{"source": "CarDekho Used", "status": "live", "listings_found": 3}],
    "results": [
        {"brand":"BMW","model":"X5","variant":"xDrive40i","price_lakh":49.5,"mfg_year":2024,"km":18000,"fuel":"Petrol","transmission":"Automatic","location":"Delhi","source":"CarDekho Used","url":"https://example.com/bmw-x5","live_verified":True,"data_consistent":True,"condition_signal":"used","body_type":"SUV"},
        {"brand":"BMW","model":"X5","variant":"xDrive30d","price_lakh":55.0,"mfg_year":2023,"km":42000,"fuel":"Diesel","transmission":"Automatic","location":"Bengaluru","source":"CarWale Used","url":"https://example.com/bmw-x5-2","live_verified":True,"data_consistent":True,"condition_signal":"used","body_type":"SUV"},
        {"brand":"Audi","model":"Q5","variant":"Technology","price_lakh":44.0,"mfg_year":2025,"km":8000,"fuel":"Petrol","transmission":"Automatic","location":"Mumbai","source":"CarDekho Used","url":"https://example.com/audi-q5","live_verified":True,"data_consistent":True,"condition_signal":"demo","body_type":"SUV"}
    ]
}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        async def route(route):
            u = route.request.url
            if "/api/catalog" in u:
                if "brand=" in u:
                    body = {"ok": True, "mode": "live", "models": [{"name": "X5"}, {"name": "X3"}]}
                else:
                    body = {"ok": True, "mode": "live", "brands": [{"name": "BMW"}, {"name": "Audi"}]}
                await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
            elif "/api/search" in u:
                await route.fulfill(status=200, content_type="application/json", body=json.dumps(RESULT))
            else:
                await route.continue_()

        await page.route("**/api/**", route)
        await page.goto("http://127.0.0.1:4173/index.html")
        await page.wait_for_load_state("domcontentloaded")
        await page.locator("#search").click()
        await page.locator(".card").first.wait_for()

        matrix = await page.evaluate("""(records) => {
            const conditions = ["both","used","demo"];
            const prices = [[null,null],[null,50],[45,50],[50,60],[0,44]];
            const fuels = [[],["petrol"],["diesel"],["electric"],["hybrid"],["petrol","diesel"]];
            const cities = ["","Delhi","Bengaluru","Mumbai"];\n            const destinations = ["Bengaluru","Delhi","Mumbai","Pune"];
            const ages = [null,2,3,5,7];
            const quick = ["","petrol","diesel","electric","hybrid","suv","sedan"];
            const year = new Date().getFullYear();
            let tested=0, failures=[];
            for (const condition of conditions) for (const price of prices)
            for (const fs of fuels) for (const city of cities)
            for (const maxAge of ages) for (const q of quick) for (const destination of destinations) {
                document.querySelector("#condition").value=condition;\n                document.querySelector("#destination").value=destination;
                document.querySelector("#city").value=city;
                document.querySelector("#year").value=maxAge===null?"":String(maxAge);
                document.querySelector("#fmin").value=price[0]===null?"":String(price[0]);
                document.querySelector("#fmax").value=price[1]===null?"":String(price[1]);
                document.querySelectorAll(".fuelCheck").forEach(x=>x.checked=fs.includes(x.value));
                quickFilter=q;
                applyResults();
                const expected=records.filter(v=>{
                    const c=conditionOf(v);
                    if(condition!=="both" && c!==condition) return false;
                    if(city && v.location!==city) return false;
                    if(price[0]!==null && !(v.price_lakh!=null && Number(v.price_lakh)>=price[0])) return false;
                    if(price[1]!==null && !(v.price_lakh!=null && Number(v.price_lakh)<=price[1])) return false;
                    if(maxAge!==null && !(v.mfg_year!=null && year-Number(v.mfg_year)<=maxAge)) return false;
                    if(fs.length && !fs.includes(String(v.fuel||"").toLowerCase())) return false;
                    if(q && String(v.fuel||"").toLowerCase()!==q && String(v.body_type||"").toLowerCase()!==q) return false;
                    return true;
                }).length;
                const actual=document.querySelectorAll("#grid .card").length;
                tested++;
                if(expected!==actual && failures.length<10) failures.push({condition,price,fs,city,maxAge,q,expected,actual});
            }
            return {tested,failures};
        }""", RESULT["results"])
        expected_permutations = 3 * 5 * 6 * (1 + len({v["location"] for v in RESULT["results"]})) * 5 * 7 * (1 + len({v["location"] for v in RESULT["results"]}))
        assert matrix["tested"] == expected_permutations, matrix
        assert matrix["failures"] == [], matrix

        await page.locator("#clear").click()
        await page.locator("#condition").select_option("used")
        await page.locator("#city").select_option("Bengaluru")
        await page.locator("#fmin").fill("45")
        await page.locator("#fmax").fill("60")
        await page.locator("#year").select_option("3")
        await page.locator(".fuelCheck[value=diesel]").check()
        await page.locator(".chip[data-filter=suv]").click()
        assert await page.locator(".card").count() == 1

        await page.locator(".fuelCheck[value=petrol]").check()
        assert await page.locator(".card").count() == 1

        for q in ["petrol","diesel","electric","hybrid","suv","sedan"]:
            await page.locator(".chip").evaluate_all("(xs,q)=>xs.forEach(x=>x.classList.toggle('active',x.dataset.filter===q))", q)
            await page.evaluate("(q)=>{quickFilter=q;applyResults()}", q)
        await page.locator(".chip[data-filter='']").click()
        assert await page.locator(".card").count() == 1

        await page.locator("#clear").click()
        assert await page.locator("#fmin").input_value() == ""
        assert await page.locator("#fmax").input_value() == ""
        assert await page.locator("#year").input_value() == ""
        assert await page.locator("#city").input_value() == ""
        assert await page.locator("#condition").input_value() == "both"
        assert await page.locator("#destination").input_value() == ""
        assert await page.locator(".fuelCheck:checked").count() == 0
        assert await page.locator(".chip.active").get_attribute("data-filter") == ""
        assert await page.locator(".card").count() == 3

        if errors:
            raise AssertionError("Browser console/page errors: "+repr(errors))
        print("PASS: 50,400 sidebar filter/context permutations + interaction/reset checks")
        await browser.close()

asyncio.run(main())
