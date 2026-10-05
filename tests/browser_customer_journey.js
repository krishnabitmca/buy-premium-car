const { chromium } = require("playwright");

const base = process.env.CARSCANNER_BASE_URL || "https://buy-premium-car1.onrender.com";
const testUrl = key => { const u = new URL(base); u.searchParams.set(key, String(Date.now())); return u.toString(); };

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push("pageerror: " + e.message));
  page.on("console", m => { if (m.type() === "error") errors.push("console: " + m.text()); });

  try {
    await page.goto(testUrl("e2e"), { waitUntil: "networkidle", timeout: 90000 });
    await page.waitForSelector("#brand", { state: "visible", timeout: 15000 });
    await page.waitForFunction(() => document.querySelectorAll("#brand option").length >= 5, null, { timeout: 30000 });

    const brandCount = await page.locator("#brand option").count();
    if (brandCount < 5) throw new Error("brand dropdown has too few options: " + brandCount);

    await page.selectOption("#brand", { label: "BMW" });
    await page.waitForFunction(() => {
      const el = document.querySelector("#model");
      return el && !el.disabled && [...el.options].some(o => /X5/i.test(o.textContent || ""));
    }, null, { timeout: 30000 });

    const modelNames = await page.locator("#model option").allTextContents();
    if (!modelNames.some(x => /X5/i.test(x))) throw new Error("BMW X5 missing from model dropdown");

    const x5Label = modelNames.find(x => /X5/i.test(x));
    if (!x5Label) throw new Error("BMW X5 option was discovered but could not be selected");
    await page.selectOption("#model", { label: x5Label });
    await page.click("#search");
    await page.waitForFunction(() => {
      const grid = document.querySelector("#grid");
      return grid && !/Searching live inventory/i.test(grid.textContent || "");
    }, null, { timeout: 90000 });

    const body = await page.locator("body").innerText();
    if (/Live models unavailable/i.test(body)) throw new Error("model catalog fell into unavailable state");
    if (/Unexpected error|Search failed|Application error/i.test(body)) throw new Error("customer-facing error shown");

    console.log(JSON.stringify({
      pass: true,
      brandCount,
      modelCount: modelNames.length,
      hasX5: true,
      resultCards: await page.locator(".card").count(),
      errors
    }));
    if (errors.length) throw new Error("browser errors: " + errors.join(" | "));
  } finally {
    await browser.close();
  }
})().catch(err => {
  console.error(err.stack || err);
  process.exit(1);
});
