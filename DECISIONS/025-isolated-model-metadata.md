# 025: Isolate observed model metadata from external enrichment

A production Honda cold-load check reached the catalogue-unavailable state even
though model requests no longer blocked HTTP threads. Database observations and
external enrichment still shared the same executor, so two slow external calls
could delay new observed-model lookups beyond the browser's eight-second budget.

Use separate two-thread executors for observed database metadata and external
catalogue enrichment. Give each queue an independent 16-key pending bound and
coalesce repeated requests by brand. Saturating enrichment must not reserve all
observed-lookup admission. Brand discovery retains its existing single pending
task on the external executor. Cached public model names remain a bounded 64-brand
LRU and never establish inventory availability.

Publish observed names before attempting external enrichment. Retain known names
during errors. Use 30-second backoff for a successful empty observed lookup, but
only one second after a failed database lookup; a timeout does not prove an empty
catalogue. External empty/error responses must preserve the existing retry deadline
and known names rather than extending failed observed lookups to 30 seconds.
External submission or
fetch failure must release its own pending slot; observed lookup always releases
its slot even when enrichment cannot be submitted. Keep existing bounded database
budgets and retryable HTTP warming status. No source activation, inventory write,
paid resource or thread-count change in Gunicorn.

Tests hold the external queue unexecuted/full and prove Honda/BMW observed metadata
can still load, alongside single-flight, expiry, failure and HTTP retry checks.
Additional regressions simulate a failed first observed lookup and require Q5
to become selectable after one second even if external enrichment is empty/fails.
External completion merges atomically with the latest cached models, preserving
newer observed family names and their canonical spelling. It must not republish
the observed snapshot captured when a slow external job was first scheduled.
Since catalogue GETs perform no synchronous database/provider work, exempt them
from expensive API admission so the reserved HTTP thread can serve cached names
and warming responses while three searches are active. Background queue bounds
still apply. A concurrent regression holds all search slots and checks both brand
and model catalogue responses without weakening search overload rejection.
This addresses metadata dependency isolation; a provider/database outage can still
make unseen models unavailable, and no national latency SLA is established.
