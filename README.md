# Buy Premium Car — Premium Car Deal Radar

India-wide premium used/demo car research system.

## Target
- Budget: <= ₹40 lakh
- Vehicle age: <= 4 years
- Prefer low mileage, 1st owner, certified/demo inventory
- Exclude stale/sold/duplicate or inconsistent listings

## Components
- Static dashboard at `index.html`
- Python crawler under `src/`
- Source configuration under `config/`
- Daily GitHub Actions crawl under `.github/workflows/daily-crawl.yml`
- Historical SQLite data and reports under `data/` and `reports/`

## Verification philosophy
A search result is not treated as proof of availability. The crawler requires a reachable vehicle page, checks sold/unavailable markers, compares manufacturing and registration data, and retains verification notes when fields are missing.

## Branch
The working implementation is on `premium-car-deal-radar`.

## Vercel
Deploy this repository using the repository root. The dashboard loads `data/latest.json`.
