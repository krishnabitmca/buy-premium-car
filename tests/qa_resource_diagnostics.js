"use strict";
function formatFailedRequest(request) {
  // Never log signed URL paths, query strings, or credentials.
  let origin = "<invalid-url>";
  try {
    const url = new URL(request.url());
    if (url.protocol === "http:" || url.protocol === "https:") origin = url.origin;
  } catch (_) {}
  const type = String(request.resourceType() || "unknown").slice(0, 40);
  const failure = request.failure();
  const reason = String((failure && failure.errorText) || "unknown").slice(0, 120);
  return "requestfailed: " + type + " " + origin + " " + reason;
}
module.exports = { formatFailedRequest };
