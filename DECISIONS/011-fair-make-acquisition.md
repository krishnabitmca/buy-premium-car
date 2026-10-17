# ADR 011 — Independent make identity and fair acquisition

The 17 October coverage audit found Hyundai and Skoda jobs waiting since
11 October, while high-priority resumable scans kept taking worker slots.
Mahindra was selectable in the UI but absent from registry-derived recognition
and baseline acquisition. Direct verified adapters could fetch all three makes.

Supplement registry capabilities with the existing independent make taxonomy for
recognition and baseline scheduling. Source routes and execution remain governed
by enabled, live, verified adapters; a make name is not coverage evidence.
This extends ADR 007's registry-only baseline. Normalize new queue keys to lower
case and preserve waiting age when the scheduler updates queued work.

Choose work from the least recently attempted brand first, then the least
recently attempted job within that brand, before demand priority and queue age.
The single-job worker updates service timestamps between claims. High-demand
continuations retain progress without indefinitely starving unserved makes or
sources. Retrying failed work remains bounded. Historical case-variant queue
rows are preserved; normal scheduling no longer creates further variants.

Run the existing bounded ten-job GitHub worker every 15 minutes. No new paid
service is provisioned. Focused recovery accepts repeatable --brand and --source
filters while retaining the same verified-source gate, claim locks and ingestion.

Show retained criteria to buyers and offer an explicit empty-state action to
search the same brand without refinements. Do not silently relax constraints.
An empty partial index is a coverage gap, not evidence that marketplaces failed
or that no cars exist. Validate real multi-source observations for non-example
makes; a bounded recovery batch is not catalogue completeness or national scale.
