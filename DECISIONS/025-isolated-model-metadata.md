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
during errors and use 30-second negative/error backoff. External submission or
fetch failure must release its own pending slot; observed lookup always releases
its slot even when enrichment cannot be submitted. Keep existing bounded database
budgets and retryable HTTP warming status. No source activation, inventory write,
paid resource or thread-count change in Gunicorn.

Tests hold the external queue unexecuted/full and prove Honda/BMW observed metadata
can still load, alongside single-flight, expiry, failure and HTTP retry checks.
This addresses metadata dependency isolation; a provider/database outage can still
make unseen models unavailable, and no national latency SLA is established.
