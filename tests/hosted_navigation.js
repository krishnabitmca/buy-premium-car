"use strict";

/**
 * Give a hosted Render instance time to wake after an HTTP 5xx.
 * This retries only server failures; 4xx responses and broken page content
 * remain hard failures in the calling browser contract.
 */
async function navigateWithServerRetry(page, makeUrl, options = {}) {
  const timeoutMs = options.timeoutMs ?? 120000;
  const retryDelayMs = options.retryDelayMs ?? 5000;
  const now = options.now ?? Date.now;
  const sleep = options.sleep ?? (ms => page.waitForTimeout(ms));
  const deadline = now() + timeoutMs;
  let response;
  do {
    response = await page.goto(makeUrl(), {
      waitUntil: "networkidle",
      timeout: Math.max(1000, Math.min(30000, deadline - now())),
    });
    if (response && response.status() < 500) return response;
    const remaining = deadline - now();
    if (remaining <= 0) return response;
    await sleep(Math.min(retryDelayMs, remaining));
  } while (true);
}

module.exports = { navigateWithServerRetry };
