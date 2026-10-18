# 015: Discovery and listing renewal are separate durable workloads

Customer value requires both new inventory and current availability. Catalogue
pagination alone cannot prove that an old listing was revisited. Large make/model
queues also starved global demo-capable sources. On October 17, demo offers still
carried October 11 verification timestamps despite successful acquisition jobs.

## Decision

Keep canonical Postgres listings and observations. Add a private listing renewal
queue, shared background crawl leases and pipeline run evidence, all with RLS and
no browser grants. One durable row per listing avoids duplicate renewal work.
Claims use SKIP LOCKED, expiring tokens, bounded backoff and daily probation after
repeated failures. Retain history; hide expired offers rather than deleting rows.

Default renewal targets are at most six hours for used and three hours for demo
offers, respecting stricter source targets. Search expiry is capped at 48 hours
for used and 24 hours for demo, or the source/global policy if stricter. These are
policy targets, not a claim that free infrastructure can meet them. Search,
watches, expiry maintenance and Elasticsearch snapshot validity share the policy.

Only exact-URL, identity-matching structured products with explicit INR offers
and availability renew an individual listing. Missing or ambiguous markup does
not renew verification time. No catalogue/sample omission implies sold status.
Demo renewal additionally requires current per-listing demo evidence. An
available product with unconfirmed demo classification is quarantined as stale,
without calling it sold or converting it to used inventory.
Two consecutive HTTP 404/410 checks, separated by at least an hour, remove an
offer; network/403/429/5xx errors never do, and reset that missing sequence.
Redirects to another listing, login page or origin fail closed.

Reviewed card-local sold/booked evidence on a previously indexed URL retires that
source offer during catalogue acquisition. Other sources for the physical car
remain eligible. All negative evidence is retained in observation history.
Claim tokens and last-verification fences prevent stale workers overwriting
newer evidence. Catalogue ingestion and checkpoint completion commit together
after rechecking ownership; no database transaction spans HTTP work.

Domain leases serialize background jobs across discovery and renewal, with a
cooldown and explicit Retry-After handling for renewal blocks. They are job-level
origin limits, not a guarantee of a global provider API requests-per-second SLA.
Interactive search and model metadata do not acquire these worker leases.

The existing ten-job quarter-hour acquisition budget becomes one general, one
demo-capable global scan, three model, three continuation and two city/dealer
catalogue jobs. An additional bounded ten-listing renewal pass alternates used
and demo slots. Renewal/expiry runs even if catalogue acquisition fails, then
refreshes the derived index. Artifacts include overdue counts, outcomes, expiry
and heartbeat evidence. The standalone worker runs both workloads without buyer
traffic and supports a continuously running deployment.

## Limits and operations

Observed free GitHub scheduled dispatch gaps were several hours, so a requested
15-minute cron is not an availability SLA. Heartbeat gaps over an hour are
reported explicitly. A production always-on worker must be provisioned with an
agreed budget before promising timely renewal across the whole inventory. No paid
service, new credential or outbound customer notification is enabled here.
Pages without sufficient per-listing evidence remain inconclusive and need an
additional reviewed parser or provider feed; old evidence must expire meanwhile.
