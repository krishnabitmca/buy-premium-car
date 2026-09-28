# Used & Demo Car Deal Radar

India-wide used and demo car research system.

## Product scope
- **All car makes and models** — customer searches are not restricted to a hardcoded model whitelist. The normalizer has a broad make/alias taxonomy and a generic model fallback so mainstream, premium, discontinued and imported listings can still be represented.
- **All cities in India** — location matching is not restricted to a fixed city allow-list. The crawler searches India-wide and uses city hints only to improve discovery of local dealer inventory.
- Current radar defaults: <= ₹40 lakh and vehicle age <= 4 years.
- Prefer low mileage, 1st owner, certified/demo inventory.
- Exclude stale, sold, duplicate or inconsistent listings.

The current price/age thresholds are **radar defaults**, not permanent limits on the future customer-intent model.

## Components
- Static dashboard at `index.html`
- Python crawler under `src/`
- Source configuration under `config/`
- Daily GitHub Actions crawl under `.github/workflows/daily-crawl.yml`
- Historical SQLite data and reports under `data/` and `reports/`
- Generic deal-intent engine under `src/deal_engine.py`

## Verification philosophy
A search result is not treated as proof of availability. The crawler requires a reachable vehicle page, checks sold/unavailable markers, compares manufacturing and registration data, and retains verification notes when fields are missing.

## Geography
India is the product market. A future customer can specify any Indian city, district or locality; the matching layer will not reject it because it is absent from a static city list.

## Vercel
Deploy this repository using the repository root. The dashboard loads `data/latest.json`.

## Customer Car Watches

The dashboard supports customer-specific Deal Intents with optional budget, vehicle-age, mileage, ownership, fuel, transmission, location/radius, condition, must-have, nice-to-have and avoid criteria.

The crawler intentionally collects a broader inventory than any one customer's constraints. Customer budget and age are applied at match time.

## Persistence and notifications

The MVP includes a Vercel Python API at `api/watch.py` and a Supabase schema at `supabase/migrations/001_deal_watch.sql`.

Configure these deployment variables to persist watches:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

For Email delivery, add:
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`

For WhatsApp delivery, add:
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_TEMPLATE_NAME`
- `WHATSAPP_TEMPLATE_LANGUAGE`
- `WHATSAPP_GRAPH_VERSION`

Optional:
- `APP_BASE_URL`

GitHub Actions runs the alert processor after the market crawl when Supabase is configured. Until provider credentials are configured, no live notifications are sent.

The dashboard explicitly records separate Email and WhatsApp consent. WhatsApp should only be enabled when the user has intentionally opted in.
