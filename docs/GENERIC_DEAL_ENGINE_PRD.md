# Personal Deal Intelligence Engine — Market Research & Product Requirements

## Executive thesis
The customer does not really want a list of products. They want help finding one purchase that fits their needs at a genuinely attractive price, with enough evidence to act.

The core abstraction should therefore be **Deal Intent**, not a car or a product category:
“Tell us what you want, what matters, what you can spend, where you are, and how good the deal must be. We watch the market and bring you back only when something worth investigating appears.”

The current premium-car radar becomes the first category adapter.

## Market evidence
- Redseer estimated India's used-car market at about $53B in 2026 and projected $68–78B by FY31; it also reported 65% of used-car buyers are first-time buyers. It describes fragmented supply and an average of about 2.1 intermediaries per transaction. 
- Recent India/Bengaluru buyer discussions repeatedly describe inflated prices, fragmented listings, hidden history/condition issues, seller ambiguity and the time required to compare sources. One September 2026 Bengaluru luxury-car post explicitly described checking six sources and building a tracker because it was difficult to know whether a listing was actually competitive. These are qualitative signals, not population estimates.
- Generic price tracking is already a validated market: Google offers price tracking in India with target prices, mobile notifications and email; Buyhatke says it covers 1,000+ stores and has a Smart Deal Scanner; several Indian apps now offer watchlists, price history and price-drop alerts.

## Product differentiation
“Price alert” alone is not enough.

The differentiation should be:
1. Need-based discovery — the buyer can describe the outcome, not an exact URL.
2. Cross-source discovery — find fragmented inventory across marketplaces, dealers and local sources.
3. Fair-value reasoning — compare against market evidence rather than MRP alone.
4. Total-cost reasoning — include transfer, tax, delivery, insurance, maintenance and other category-specific costs where relevant.
5. Confidence and risk — explicitly distinguish strong evidence from missing/contradictory data.
6. Low-noise personalization — alert only when the user's own threshold is met.
7. Category adapters — the same engine can serve automotive, electronics, travel, appliances and other high-consideration purchases.

## Ideal customer profile
### A — High-consideration buyer
Time-poor professional with a defined buying window, several constraints, flexibility on the exact seller/model and willingness to wait for a materially better opportunity.

### B — Spec-aware bargain hunter
Knows requirements but not the fair market price.

Example:
“32GB RAM, OLED, good battery, under ₹1 lakh; I am willing to wait.”

### C — Upgrade/replacement buyer
Has a desired quality level but is waiting for the price to reach a personal threshold.

### Not the first target
Urgent purchases and very low-value commodity purchases where the savings are too small to justify monitoring.

## Generic user journey
1. Tell us what you want using natural language.
2. Engine converts the request into structured constraints.
3. User chooses alert sensitivity: exceptional, good, or any match.
4. User selects notification channels.
5. Engine continuously/daily evaluates new listings, price changes, stock changes and market-value changes.
6. Only meaningful matches generate alerts.
7. Alert links back to an evidence-rich dashboard.

## Example alert
“Deal Watch hit — 2024 BMW X1 xDrive20i — ₹39.2L vs estimated fair value ₹43.0L — 11,800 km — 1 owner — Delhi — confidence 0.86 — main risk: Bangalore transfer/tax not verified — Open dashboard.”

## Generic data model
User: user_id, email, phone, timezone, status, created_at
DealIntent: intent_id, user_id, category, natural_language_request, structured_constraints, target_discount, status
ChannelPreference: user_id, channel, enabled, categories, frequency, consent_at, consent_source
Listing: listing_id, category, source, canonical_url, title, images, location, availability
Observation: listing_id, observed_at, price, stock, metadata_hash
Evaluation: listing_id, intent_id, match_score, deal_score, confidence, fair_value, total_cost, reasons, risks
AlertEvent: alert_id, user_id, intent_id, listing_id, channel, reason, sent_at, opened_at, status

## Architecture
Sources → crawler/API adapters → normalizer/entity resolver → listing + observation store → category evaluator → generic deal engine → intent matcher → alert policy/deduplication → email/WhatsApp → personal dashboard.

The generic engine should NOT contain automotive fair-value logic. Automotive owns VIN/date/mileage/comparables/landed-cost rules; electronics can own model/variant/retailer/coupon rules; travel can own route/date/baggage rules.

## Notification design
Use an alert outbox:
Evaluation → AlertEvent(PENDING) → dispatcher → provider → SENT/FAILED.

Add per-user cooldowns, duplicate suppression, daily caps, per-intent pause, channel-level opt-out and consent audit records.

WhatsApp Business requires explicit opt-in for subsequent messages. Business-initiated conversations use approved message templates, while free-form replies are available within the 24-hour customer-service window. This makes explicit, separate consent for WhatsApp a product requirement.

## MVP registration UX
CTA: “Tell us what you want.”

Fields:
- What are you looking for?
- Category
- Budget
- Location / radius
- Must-haves
- Nice-to-haves
- Avoid
- How good must the deal be?
- Email
- WhatsApp number
- Email alerts checkbox
- WhatsApp alerts checkbox
- Frequency: instant / daily digest
- Pause / unsubscribe controls

Use passwordless email login or a magic-link account rather than a password-heavy registration flow.

## 30-day customer discovery
Week 1: 20 interviews — 10 used-car, 5 laptop/phone, 5 other high-ticket buyers.
Week 2: landing page + waitlist + first Deal Intent.
Week 3: manually-assisted alerts for the first 50 users.
Week 4: measure intent completion, time to first useful match, alert open rate, dashboard return, false-positive rate and “I would actually buy this” feedback.

## Beachhead sequence
1. Premium/used cars — the current engine already has the source and verification foundation.
2. Laptops/phones around large sales — natural language needs and price thresholds are common.
3. Cameras, TVs, appliances, motorcycles.
4. Other fragmented, high-value markets after the evaluation adapter exists.

## MVP stack
Vercel for web/API, Supabase for users/intents/preferences/alert events, GitHub Actions for current crawler orchestration, Resend for transactional email, Meta WhatsApp Cloud API or Twilio for WhatsApp.

Supabase currently lists a free tier with 50k MAU, 500MB database and 500k Edge Function invocations. Resend lists 3,000 free emails/month and 100/day. Vercel Hobby cron jobs support daily schedules, so the current daily crawler model fits an early-stage MVP.

## Business model hypothesis
Start free while validating.
Potential premium features: more active intents, faster monitoring, richer market evidence, landed-cost analysis, long price history, high-confidence alert modes and assisted verification.

Do not sell ranking placement. Trust is the product.

## North-star metric
Qualified Deal Alerts Accepted / Active Buyer.

A qualified alert should meet hard constraints, have sufficiently strong evidence, cross the user's threshold and lead to a dashboard visit.
