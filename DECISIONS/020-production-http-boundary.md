# 020: Supervised production HTTP boundary on the existing deployment

The owner selected a $150/month hardening planning envelope. This does not approve
paid-service activation. Keep PostgreSQL serving and preserve inventory behavior
while preparing a supervised, bounded web runtime for later always-on acquisition.

The Docker process now runs pinned Gunicorn with a WSGI adapter over the existing
handlers. The Windows `render_server.py` preview remains available. No search,
watch or catalogue rules are duplicated. Keep the public asset allowlist, validated
API request bodies, CORS, source provenance, timing and no-store responses.

Default to one process and four request threads, 32 worker client connections and
a 128 socket backlog. Do not preload database pools or background executors before
forking. Use a 25-second graceful restart allowance within the current Render
shutdown budget; close worker-local database pools on exit. The 45-second Gunicorn
timeout is a worker-heartbeat timeout, not a per-request deadline for gthread.
Dependency timeouts, admission policy and an end-to-end request deadline remain
separate hardening requirements. Request counts alone do not prove capacity.

`/health` remains process liveness. `/ready` separately probes database access and
canonical table presence using a one-second pool checkout budget and one-second
server statement timeout. Direct-connection probes request a one-second connect
timeout. DNS/network behavior can still affect timing. Probe failures return a
redacted 503; they do not trigger crawling or expose credentials. No health-check
setting is changed in the Render account by this commit. Adopting `/ready` as the
platform check requires evaluating shared database outage/restart behavior.

WSGI responses identify their runtime in a header, preserve HEAD body semantics
and reject oversized bodies before reading. Access logs retain method, status and
duration without raw query strings, authorization headers or buyer input. Uncaught
adapter exceptions return a generic error and log only their type.

CI runs the actual Linux process against disposable PostgreSQL, including an
in-flight locked search drained across SIGTERM, plus branch browser QA against the
production adapter. This is a serving foundation; it does not establish replica
failover, national latency, crawl coverage, distributed rate limiting or complete
indexed retrieval. No paid plan, new secret, schema or public grant is introduced.
