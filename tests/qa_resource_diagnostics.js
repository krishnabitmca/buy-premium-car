"use strict";
const RESOURCE_TYPES = new Set([
  "document", "stylesheet", "image", "media", "font", "script",
  "texttrack", "xhr", "fetch", "eventsource", "websocket", "manifest", "other"
]);
function formatFailedRequest(request) {
  // Never log signed URL paths, query strings, credentials, or arbitrary error text.
  let origin = "<invalid-url>";
  try {
    const url = new URL(request.url());
    if (url.protocol === "http:" || url.protocol === "https:") origin = url.origin;
  } catch (_) {}
  const resourceType = String(request.resourceType() || "unknown").toLowerCase();
  const type = RESOURCE_TYPES.has(resourceType) ? resourceType : "unknown";
  const failure = request.failure();
  const errorText = String((failure && failure.errorText) || "");
  // Browser network error codes are bounded, stable labels; raw error text can
  // contain signed URLs or attacker-controlled request details.
  const match = errorText.match(/^net::(ERR_CERT_[A-Z0-9_]+)$/);
  const reason = match ? "net::" + match[1] : "unknown";
  return "requestfailed: " + type + " " + origin + " " + reason;
}
module.exports = { formatFailedRequest };
