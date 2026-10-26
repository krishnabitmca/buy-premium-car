const { chromium } = require("playwright");

const base = process.env.CARSCANNER_BASE_URL || "https://buy-premium-car1.onrender.com";
const testUrl = key => { const u = new URL(base); u.searchParams.set(key, String(Date.now())); return u.toString(); };

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  const apiResponses = new Map();
  page.on("pageerror", e => errors.push("pageerror: " + e.message));
  page.on("console", m => {
    if (m.type() !== "error") return;
    // Chromium logs HTTP errors even for intentionally handled overload retries
    // and third-party images. Check actual first-party API outcomes below.
    if (/^Failed to load resource: the server responded with a status of \d+/i.test(m.text())) return;
    errors.push("console: " + m.text());
  });
  page.on("response", response => {
    const url = new URL(response.url()), request = response.request();
    if (url.origin !== new URL(base).origin || !url.pathname.startsWith('/api/')) return;
    const key = [request.method(), response.url(), request.postData() || ''].join('\n');
    apiResponses.set(key, {path: url.pathname, status: response.status()});
  });

  try {
    // Render may briefly return a 5xx during instance restart. Retry only that
    // transport failure; never treat a successfully served broken UI as passing.
    let navigation;
    for (let attempt = 0; attempt < 3; attempt++) {
      navigation = await page.goto(testUrl("e2e"), { waitUntil: "networkidle", timeout: 90000 });
      if (navigation && navigation.status() < 500) break;
      if (attempt < 2) await page.waitForTimeout(3000 * (attempt + 1));
    }
    // An E2E run against the hosted app is a production smoke check, not
    // evidence that this PR's commit was deployed. Surface that distinction.
    const expectedSha = process.env.EXPECTED_DEPLOYMENT_SHA || "";
    if (expectedSha) {
      const version = await page.request.get(new URL("/api/version", base).toString(), { timeout: 15000 });
      if (!version.ok()) throw new Error("Deployment version endpoint returned HTTP " + version.status());
      const data = await version.json();
      if (data.commit !== expectedSha) throw new Error("Hosted deployment SHA mismatch: expected " + expectedSha + ", got " + String(data.commit));
    }
    if (!navigation || navigation.status() >= 400) {
      throw new Error("Hosted application navigation failed: HTTP " + (navigation ? navigation.status() : "no response"));
    }
    try {
      await page.waitForSelector("#brand", { state: "visible", timeout: 15000 });
    } catch (err) {
      const title = await page.title().catch(() => "unavailable");
      const snippet = (await page.locator("body").innerText().catch(() => "")).slice(0, 350);
      throw new Error("Brand selector missing after HTTP " + navigation.status() +
        "; title=" + JSON.stringify(title) + "; body=" + JSON.stringify(snippet) +
        "; original=" + err.message);
    }
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
      const button = document.querySelector('#search');
      return grid && button && !button.disabled && !/Searching (?:live inventory|car listings)/i.test(grid.textContent || "");
    }, null, { timeout: 90000 });

    const body = await page.locator("body").innerText();
    if (/Live models unavailable/i.test(body)) throw new Error("model catalog fell into unavailable state");
    if (/Unexpected error|Search failed|Application error/i.test(body)) throw new Error("customer-facing error shown");

    for (const outcome of apiResponses.values()) {
      if (outcome.status >= 400) errors.push('API failure: ' + outcome.path + ' status=' + outcome.status);
    }
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
