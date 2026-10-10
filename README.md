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
- Canonical Postgres acquisition under `src/main.py` and continuous refresh under `src/inventory_service.py`
- Source configuration under `config/`
- Daily GitHub Actions crawl under `.github/workflows/daily-crawl.yml`
- Historical SQLite data and reports under `data/` and `reports/`
- Generic deal-intent engine under `src/deal_engine.py`

## Verification philosophy
A search result is not treated as proof of availability. The crawler requires a reachable vehicle page, checks sold/unavailable markers, compares manufacturing and registration data, and retains verification notes when fields are missing.

### Inventory reliability tests

Run the dependency-light tests with:

```sh
pip install -r requirements.txt "pytest>=8,<9"
python -X utf8 -m pytest -q -m "not e2e and not integration"
```

The inventory integration suite uses a real local PostgreSQL server. Point
`CARSCANNER_TEST_DATABASE_URL` at a **localhost test server** using a test administrator
that can create databases/roles. The fixture creates a random disposable database,
applies all committed Supabase SQL files, and removes only its own database afterwards.
It creates the `anon`, `authenticated` and `service_role` NOLOGIN roles if absent,
to exercise the migration grants on plain PostgreSQL. Do not use an application
or production database connection. GitHub CI provisions its own PostgreSQL service.

```sh
CARSCANNER_TEST_DATABASE_URL=postgresql://test_user:test_password@127.0.0.1:5432/postgres \
  python -X utf8 -m pytest -q -m integration tests/test_inventory_postgres.py
```

The suite replaces external marketplace acquisition with deterministic fixtures,
but uses the actual scheduler, claim/ingestion SQL and HTTP search handler.
It checks newer prices, sold/unverified observations, expiry, numeric/UUID/timestamp
JSON values, used/demo filtering, multiple offers and destination-as-context.

Production refresh commands require `SOURCE_INTELLIGENCE_DATABASE_URL` or
`DATABASE_URL`; a missing connection variable exits unsuccessfully rather than
silently reporting no work. `CARSCANNER_DATABASE_URL` is not a supported alias.

## Geography
India is the product market. A future customer can specify any Indian city, district or locality; the matching layer will not reject it because it is absent from a static city list.

## Vercel
Deploy this repository using the repository root. The dashboard calls `/api/search`;
`data/latest.json` is a legacy/reporting artifact, not a customer inventory fallback.

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

Production acquisition and watches require `SOURCE_INTELLIGENCE_DATABASE_URL` (or
`DATABASE_URL`). Apply all migrations and explicitly bootstrap/verify the source
registry before enabling workflows. Watch API credentials must refer to the same
Supabase project as the inventory connection.

```sh
python -m src.main --limit 100
python -m src.inventory_service --limit 10 --interval-seconds 60
python -m scripts.process_alerts --mode instant --dry-run
```

The daily workflow runs daily/both watches; the 15-minute refresh workflow runs
instant/both watches. Provider credentials and recorded channel consent are
required to send. Remove `--dry-run` only in a configured environment intended to
deliver alerts. See [continuous inventory operations](docs/CONTINUOUS_INVENTORY.md)
for execution, migration behavior and outstanding launch gates. Legacy browser/
SQLite reports require an explicit `python -m src.legacy_reports` invocation and
cannot feed production watch processing.

The dashboard explicitly records separate Email and WhatsApp consent. WhatsApp should only be enabled when the user has intentionally opted in.
