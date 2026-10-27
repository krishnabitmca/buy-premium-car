"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { formatFailedRequest } = require("./qa_resource_diagnostics");
test("TLS failure includes origin but no signed URL", () => {
  const diagnostic = formatFailedRequest({
    url: () => "https://user:password@images.example.test/private/car.jpg?token=secret123",
    resourceType: () => "image",
    failure: () => ({ errorText: "net::ERR_CERT_AUTHORITY_INVALID" })
  });
  assert.match(diagnostic, /image https:\/\/images\.example\.test net::ERR_CERT_AUTHORITY_INVALID/);
  assert.doesNotMatch(diagnostic, /password|private|car\.jpg|secret123/);
});
test("invalid URL cannot crash diagnostics", () => {
  const diagnostic = formatFailedRequest({
    url: () => "not a url",
    resourceType: () => "image",
    failure: () => null
  });
  assert.match(diagnostic, /<invalid-url> unknown/);
});
