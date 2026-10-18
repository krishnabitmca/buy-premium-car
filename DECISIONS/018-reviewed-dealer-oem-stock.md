# 018: Reviewed Škoda OEM stock API and Fusion dealer catalogues

Generic candidate validation missed these sources because the Škoda homepage
contains filters, while Fusion collection pages advertise brand catalogues.
Implement source-specific adapters in the existing bounded background pipeline.

Škoda's public `/buy` interface advertises `/buySearch` and page positions through
buy.js and `.page_move` controls. Mirror only that read-only stock POST. Open a
fresh cookie/CSRF session each batch, use one API ordering for every page, verify
the returned active page and persist only `next_page` under the existing OEM
cursor. Bootstrap/session requests are transport overhead, not inventory pages.
Keep the six-card public page size and share the configured page budget. A wrong
page, missing pagination or positive page without extractable cards fails the
batch, retaining the worker's previous checkpoint. This is resumable traversal,
not a snapshot or completeness guarantee as source stock changes.

Use individual stock IDs and source card asking prices, including unknown
mileage. Model-family year ranges are not vehicle manufacture dates. The OEM
programme includes multiple brands and not-certified stock: neither its name nor
new/unregistered status proves certification or demonstrator condition.

Fusion's `/collections/` advertises `/brand/.../` catalogues. Follow only these
same-host advertised routes with the existing durable frontier. Extract each
`.product` card's own URL, asking price, registration year and mileage. Exclude
sold/booked/reserved cards and record explicit negative card evidence for offers
already indexed. Do not infer manufacture year or seller location from a vehicle
registration label. Advertised brand counts include sold cards and are never
reported as available stock.

Reviewed individual-page evidence renews each listing independently: Fusion
requires the matching canonical URL and main vehicle section; Škoda requires the
matching stock ID in its vehicle image group. Match actual vehicle identity and
use only the main asking price, ignoring EMI, related cars, forms and FAQs.
Explicit unavailability retires the offer; fetch/parser failures remain errors
or inconclusive and cannot renew it. These used surfaces never establish demo
condition. Existing JSON-LD renewal evidence takes precedence when conclusive.

Enable only these reviewed adapters through an explicit rollout script after
deployment. All selected sources must first pass live priced-stock and matching
individual-detail checks. Keep discovery staging separate, disable the obsolete
Škoda homepage endpoint and remove its unsupported demo capability. No schema,
credentials, public database grants or paid infrastructure changes are required.

These two adapters expose whole catalogues, not reviewed targeted API routes.
Set `global_catalogue_only` so the scheduler creates one continuing India-wide,
both-condition catalogue intent instead of replaying the same whole catalogue
for every make, model and destination. Indexed searches still cover every brand
and model actually observed. Other sources retain their existing workload mix.

GaadiBazaar and Motodeals remain research candidates. Broad demo feeds and an
independent market benchmark remain open; these two adapters are incremental.
