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
test("network error text containing signed URLs is not logged", () => {
  const diagnostic = formatFailedRequest({
    url: () => "https://cdn.example.test/secret/image.png?sig=123",
    resourceType: () => "image",
    failure: () => ({ errorText: "net::ERR_CERT_AUTHORITY_INVALID https://cdn.example.test/private?sig=123" })
  });
  assert.equal(diagnostic, "requestfailed: image https://cdn.example.test unknown");
  assert.doesNotMatch(diagnostic, /private|secret|sig=|image\.png/);
});
test("resource types cannot inject arbitrary text into diagnostics", () => {
  const diagnostic = formatFailedRequest({
    url: () => "https://cdn.example.test/photo.jpg",
    resourceType: () => "image https://evil.test/?token=abc",
    failure: () => ({ errorText: "net::ERR_CERT_COMMON_NAME_INVALID" })
  });
  assert.equal(diagnostic, "requestfailed: unknown https://cdn.example.test net::ERR_CERT_COMMON_NAME_INVALID");
});
test("unexpected non-certificate error labels are suppressed", () => {
  const diagnostic = formatFailedRequest({
    url: () => "https://cdn.example.test/photo.jpg",
    resourceType: () => "image",
    failure: () => ({ errorText: "ERR_CONNECTION_RESET /private?token=abc" })
  });
  assert.equal(diagnostic, "requestfailed: image https://cdn.example.test unknown");
});
