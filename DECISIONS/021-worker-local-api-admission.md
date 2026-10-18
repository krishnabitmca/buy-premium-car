# 021: Bound expensive HTTP API concurrency on the free runtime

The owner chose to retain free testing rather than activate the prepared paid
services. Continue hardening code without provisioning resources.

Limit concurrent API handler execution to two requests per WSGI worker using a
nonblocking semaphore. Reject excess API work before reading its body with a
generic, no-store 503 and Retry-After: 1. Keep existing wildcard API CORS behavior.
Release admission on handler exceptions and failed response callbacks as well as
success. The adapter buffers handler output before returning, so the permit covers
all handler/dependency execution, but not the later network response transmission.

Exclude preflight and the cheap release endpoint from admission. Homepage,
liveness and readiness remain outside the API budget. With the default four
threads this leaves room to dispatch these routes during two slow API handlers.
This does not prioritize socket dispatch or guarantee health latency: clients,
backlog, body reads on admitted requests and readiness dependency calls still
consume runtime resources. Changing the thread count can remove this headroom.

The limit is worker-local, not per user or distributed: N workers admit up to 2N
API handlers. This is load shedding, not a replacement for deadlines, distributed
abuse controls, database budgets or national capacity measurements. No automatic
mutation replay is added. Browser catalogue GET and search POST (a read-only
contract) retry at most three times only for 503 with a positive Retry-After of
at most two seconds. Small jitter reduces synchronized retries. Existing overall
abort deadlines cover fetches and retry waits; cancellation stops replay. Other
statuses and mutation routes are not replayed.

Concurrent tests hold both permits, verify rejection without body reads and health
access, then prove recovery. Failure tests verify no permit leaks on handler or
start_response failure. Linux runtime and browser CI remain required before merge.
