# 024: Device-local saved choices and revalidated comparison

Provide useful buyer decision objects while verified accounts and notification
delivery remain unfinished. Explicitly label saved searches/cars as this-browser
storage, with at most five searches and six vehicle choices. Do not describe them
as account sync, alerts or delivery. Storage failure leaves tab-local choices with
an explicit message; no secret, AI prompt or price snapshot is persisted.

Save/share typed search criteria after validation through the existing server
SearchIntent parser. `/api/intent` accepts `validate_only: true` without invoking a
model, reserving AI quota or interpreting unknown criteria. Shared search JSON is
versioned in a URL fragment, includes filters/destination, and is validated again
before restoration. Invalid/unsupported state is not silently executed. Use the
same form application and indexed search contract; never impose destination as
seller geography. Share controls disclose the contents before copying the link.

`POST /api/shortlist` accepts at most six public vehicle UUIDs and reads current
canonical eligible offers using the existing ID-hydration query. Original
comparison cohorts remain independent of the selected IDs. Latest sold/expiry/
source-disable policy still applies. Ignore client-supplied prices/results; do
not substitute stored offers after a database or network failure. This endpoint
reads public inventory only and does not grant access to buyer/watch records.

Only rechecked offers with the originally saved price basis can enter comparison.
Compare at most three distinct saved vehicle IDs, with observed prices, basis,
year/mileage/fuel/transmission/location/times, sources and original links. Keep
unknowns explicit and warn that different price bases are not directly comparable.
Source observations are not physical-availability, inspection or seller guarantees.

Use the existing accessible dialog/focus behavior. Offline detection clears saved
offer revalidation state; reconnect can recheck the identifiers. Existing result
cards are labelled earlier observations during an outage. No inventory/price cache
or service worker is introduced: cold offline launch/PWA remains unfinished.

This delivers a device-local subset of product gates 4/5. Verified accounts,
cross-device persistence, controlled watch delivery, advanced shareable dossiers,
real-device accessibility acceptance and mobile application distribution remain
open. No new paid service, notification send, credential or database schema.

Four-tab QA also exposed cold model metadata holding API admission while duplicate
requests waited on a synchronous load. Model HTTP now returns cached names or a
no-store 503/Retry-After while one bounded background task loads observed metadata
and enriches it. Publish observed names before contacting external catalogues.
Keep at most 16 pending model tasks/two executor threads and 64 cached brands;
serve stale model names during refresh (never stale inventory prices). Empty/error
loads back off 30 seconds. Database metadata uses a two-second pool checkout and
one-second statement timeout; transport timing is not an end-to-end SLA.
