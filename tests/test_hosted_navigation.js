"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { navigateWithServerRetry } = require("./hosted_navigation");

function fixture(statuses) {
  let clock = 0;
  const calls = [];
  const page = {
    goto: async (url, options) => {
      calls.push({ url, options });
      const status = statuses[Math.min(calls.length - 1, statuses.length - 1)];
      return { status: () => status };
    },
  };
  return {
    page, calls, now: () => clock,
    sleep: async ms => { clock += ms; },
    elapsed: () => clock,
  };
}

test("recovers from transient hosted 503 without ignoring a later 200", async () => {
  const f = fixture([503, 503, 200]);
  const response = await navigateWithServerRetry(f.page, () => "/?e2e=1", f);
  assert.equal(response.status(), 200);
  assert.equal(f.calls.length, 3);
  assert.equal(f.elapsed(), 10000);
  assert.ok(f.calls.every(c => c.options.waitUntil === "networkidle"));
});

test("does not retry a client error that should fail the browser contract", async () => {
  const f = fixture([404, 200]);
  const response = await navigateWithServerRetry(f.page, () => "/", f);
  assert.equal(response.status(), 404);
  assert.equal(f.calls.length, 1);
});

test("persistent 503 remains a failure after the bounded deadline", async () => {
  const f = fixture([503]);
  const response = await navigateWithServerRetry(f.page, () => "/", {
    ...f, timeoutMs: 12000, retryDelayMs: 5000,
  });
  assert.equal(response.status(), 503);
  assert.equal(f.elapsed(), 12000);
  assert.equal(f.calls.length, 4);
});

test("does not retry successful hosted responses", async () => {
  const f = fixture([200, 503]);
  const response = await navigateWithServerRetry(f.page, () => "/", f);
  assert.equal(response.status(), 200);
  assert.equal(f.calls.length, 1);
});
