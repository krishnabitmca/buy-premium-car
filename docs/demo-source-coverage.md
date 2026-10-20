# Demo source coverage audit — 2026-10-08

| Seller | Inventory surface | Decision |
|---|---|---|
| Sundaram Motors | https://sundarammotorspoc.com/listings/ | Adapter implemented from current active individual cards with explicit Demo condition and asking price. Deployment preview returned HTTP 403; report unavailable rather than cached results. Follow advertised numbered pages, cap ten; page failures remain visible. |
| Gurudev Tata | https://gurudevtata.in/quotations/api/demo-stock/public | Live: public feed used by dealer demo page. Current response contains one Altroz; older indexed four-car inventory is not current proof. On-road Chennai price, unknown mileage and no actual vehicle photos preserved. |
| Big Boy Toyz | https://www.bigboytoyz.com/collection?demo=1 | Add endpoint to existing live seller. Only individual product isDemo evidence qualifies; unregistered alone does not. |
| DiscountedCarsIndia | https://www.discountedcarsindia.com/cars?category=demo | Reviewed: current demo category empty. Do not reclassify new/unregistered stock. |
| MT Motors | https://mtmotors.in/ | Reviewed: site explicitly says no exact unit verified live; model pages are not listings. |
| MR Automotive | https://mr-automotive.in/ | Research lead: homepage cards lack asking prices and individual demo condition. Not enabled. |
| MotorIQ | https://motoriq.in/used-cars | Research lead: indexed MG demo not on fetched current first inventory page. Not enabled without current demo proof. |
| Motodeals | https://www.motodeals.co.in/ | Research lead: fetch timed out; not verified. |
| Gurudev Skoda | https://gurudevmotors.com/skoda-demo-cars-sale/ | Campaign lead; not enabled without individually priced current units. |
| GetOnRoadPrice | https://www.getonroadprice.com/demo-cars/india | Indexed demo units have quote-only prices; current direct fetch timed out. Not enabled. |
| Group Landmark | https://www.grouplandmark.in/ | Dealer lead; demo articles are not current individual inventory. |

Existing OEM Mercedes-Benz, BMW and Motozite feeds remain aggregated. Coverage is incremental, not a claim to have exhaustively searched every Indian dealer. Dealer website observation is not independent confirmation that a vehicle remains unsold. Live API reports each source's status and match count.

## 20 October 2026 investigation

Production All brands / Demo only returned cards; BMW Demo returned zero. At the
checked snapshot, 72 eligible source offers were all Mercedes-Benz (60 OEM and
12 Motozite), not evidence of all-brand supply or unique physical cars. BMW's
brandless demo queue used its generic used-stock root because query routing
required a brand. The adapter now selects only explicitly configured literal
condition routes and restarts old-root generations. It never relabels unknown
or ordinary used offers as demos.

Sundaram and Gurudev Tata exist in YAML/code but were absent from the live source
registry. Sundaram's current public page advertises explicit Mercedes demo cards;
its previously recorded deployment 403 still requires worker verification.
Gurudev's public demo-stock endpoint currently exposes one priced Altroz offer.
Its parser rejects malformed/invalid prices and fails closed if multiple items
lack individual offer identity. Review actual ingestion before claiming rollout.
No indexed-result absence establishes no demos in the market. Wider OEM/dealer
feeds and sustained acquisition remain open; this is a bounded defect fix.
