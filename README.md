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
