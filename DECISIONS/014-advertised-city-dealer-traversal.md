# 014: Traverse advertised city and dealer catalogues

National make/model routes are insufficient: marketplace roots expose only a
sample, city pages expose more local inventory, and dealer homepages expose
featured stock. Acquisition must reach these surfaces without tying inventory
to the buyer's registration destination.

Use the existing global, both-condition refresh job as a durable breadth-first
frontier. Only follow same-host city links matching reviewed source-specific
path and title patterns, and reviewed advertised dealer catalogue links. Persist
scope provenance, pending URLs, visited URLs and advertised totals with the
existing continuation. Keep claims, retries, idempotent ingestion and source
failure isolation. Do not create guessed city routes or brand × city job grids.

Reserve two of ten quarter-hour jobs for these global catalogues. The remaining
allocation is two general, three model and three continuation jobs. No new paid
infrastructure or schema is required. A successful batch advances the cursor;
a failed batch retains its previous cursor. Positive advertised stock with zero
extracted cards is an extraction failure, not a successful empty catalogue.

Luxury Ride's full catalogue has a different card shape from its homepage.
Extract stable listing IDs, price units, outlet labels, photos and original URLs;
exclude sold/booked/reserved cards. Its WordPress paged links redirect to a page
showing page one. The public tf-car-listing taxonomy.js maps these clicks to the
read-only filter_archive_listing_ajax API with queryData=page=N. Mirror that
observed contract, normalize the response's advertised next link, and validate
that the response's current page matches the requested page. Do not manufacture
page counts or silently accept repeated page-one responses.

Operational coverage reports expose catalogue progress and last errors.
Advertised totals are source claims, not verified unique available inventory.
Even exhaustion of advertised links is `traversal_exhausted_unverified`, never
proof of complete market coverage. Source partnerships/feeds and additional
reviewed adapters remain necessary for inventory that public pages omit.
