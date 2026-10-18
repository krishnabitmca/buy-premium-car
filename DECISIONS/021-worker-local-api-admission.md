# 021: Bound expensive HTTP API concurrency on the free runtime

The owner chose to retain free testing rather than activate the prepared paid
services. Continue hardening code without provisioning resources.

Limit concurrent API handler execution to three requests per WSGI worker using a
nonblocking semaphore. Reject excess API work before reading its body with a
generic, no-store 503 and Retry-After: 1. Keep existing wildcard API CORS behavior.
Release admission on handler exceptions and failed response callbacks as well as
success. The adapter buffers handler output before returning, so the permit covers
all handler/dependency execution, but not the later network response transmission.

Exclude preflight and the cheap release endpoint from admission. Homepage,
liveness and readiness remain outside the API budget. With the default four
threads this leaves one thread to dispatch these routes during three slow API handlers.
This does not prioritize socket dispatch or guarantee health latency: clients,
backlog, body reads on admitted requests and readiness dependency calls still
consume runtime resources. Changing the thread count can remove this headroom.

The limit is worker-local, not per user or distributed: N workers admit up to 3N
API handlers. This is load shedding, not a replacement for deadlines, distributed
abuse controls, database budgets or national capacity measurements. No automatic
mutation replay is added. Browser catalogue GET and search POST (a read-only
contract) retry at most three times only for 503 with a positive Retry-After of
at most two seconds. Small jitter reduces synchronized retries. Existing overall
abort deadlines cover fetches and retry waits; cancellation stops replay. Other
statuses and mutation routes are not replayed.

Brand catalogue HTTP returns the make taxonomy plus previously discovered public
metadata immediately. At most one enrichment task is pending per worker, using
the existing bounded metadata executor. Refresh after 15 minutes on success,
back off 30 seconds on failure/empty discovery and retain prior metadata. This
does not cache vehicle prices or availability; taxonomy entries remain labelled
as unverified inventory coverage. Model lookup behavior is preserved.

Concurrent tests hold all three permits, verify rejection without body reads and health
access, then prove recovery. Failure tests verify no permit leaks on handler or
start_response failure. Linux runtime and browser CI remain required before merge.
