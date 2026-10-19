# 027: Opt-in AI evidence selection with server-rendered facts

Add a buyer evidence guide to the existing public offer dossier. A request supplies
only a public vehicle UUID, its selected price basis, a car question and explicit
Gemini consent. The server retrieves eligible canonical offers itself; it never
accepts client facts, prices, source URLs or generated answers as evidence.

Use the existing Gemini free-testing configuration and shared durable daily cap
of at most 30 calls, including failures. Do not add billing, a paid fallback,
stored prompts or notification delivery. Reject contact details/links in questions
before quota/provider work. Keep AI off the initial search critical path.

The model selects relevant evidence IDs and unknown-evidence categories in a
small JSON response. Validate every ID/category and reject additional fields,
duplicates, unbounded responses and incomplete output. The server renders all
fact text, amounts, source links and observation timestamps from its retrieved
registry. No model-authored factual prose, valuation, inspection or availability
claim is displayed. Normalized vehicle attributes are explicitly canonical-record
attributes, rather than falsely attributed to one particular source offer.

Always explain that source observations are not physical availability, coverage
is partial, grouped identity needs seller confirmation, and accident/warranty/
service/inspection/landed-cost evidence is not established by this dossier.
Return an abstention when no relevant supported fact is selected. Price bases
remain separate; no cross-basis minimum is calculated.

This is constrained evidence selection, not unrestricted generated advice. Tests
verify server retrieval, citation integrity, stale/sold absence, consent/privacy,
quota failure, prompt-injection-shaped output and API/browser error behavior.
Real held-out intent/question relevance, multilingual quality and buyer evaluation
remain open acceptance gates; schema validity alone cannot establish relevance.

Provider reference: https://ai.google.dev/gemini-api/docs/structured-output

Production diagnosis recorded a provider transport TimeoutError at eight seconds.
For evidence selection on Gemini 3 models, explicitly request supported `low`
thinking, allow up to 1,500 output tokens and a 15-second transport timeout. The
browser guide allows 30 seconds for database plus provider work. These are bounded
configuration budgets, not end-to-end latency guarantees. Intent interpretation
retains its existing transport settings.

Share one nonblocking optional-AI slot per HTTP worker between interpretation and
the guide. Reject excess AI requests before database/quota/provider work, release
the slot on every exit, and retain ordinary search/typed validation capacity.
The durable 30/day quota still applies across workers and failures. Never retry
an AI request automatically. Low reasoning is explicitly supported by the current
Gemini 3.8 model; do not use its unsupported `minimal` setting.

Provider control reference:
https://ai.google.dev/gemini-api/docs/generate-content/thinking

The live Render request still timed out after explicit low thinking and fifteen
seconds. Give the simpler evidence-ID selection task its own model setting,
`CARSCANNER_GEMINI_EVIDENCE_MODEL`, defaulting to Gemini 3.1 Flash-Lite with its
supported minimal thinking. Retain the existing Gemini 3.8 intent pilot setting.
Google's current model/pricing documentation identifies Flash-Lite as suitable for
lightweight, low-latency tasks and offers a free API tier. Reuse the approved free
project/key and durable cap; do not enable billing or automatic paid fallback.
Transport remains fifteen seconds. Distinguish response-header wait from body
read in redacted diagnostics. Real deployed validation and relevance evaluation
remain required; a different model is not evidence of successful service.

References:
- https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite
- https://ai.google.dev/gemini-api/docs/pricing#gemini-3.1-flash-lite

The deployed lightweight model successfully selected cited price/mileage facts.
An unsupported accident/warranty question completed generation but failed local
selection validation. Supply a provider JSON schema with exact evidence-ID and
unknown-category enums, required bounded arrays and no extra properties, including
an explicit empty-facts abstention path. Retain all local validation: schema
validity does not prove semantic relevance or physical facts. Never accept or
silently remap an invented evidence/category ID merely to make generation succeed.
Reference: https://ai.google.dev/gemini-api/docs/generate-content/structured-output

Use `responseMimeType` plus `responseJsonSchema` on the current generateContent
request. A counted Gemini 3.1 Flash-Lite request with this schema returned empty
fact IDs and inspection/warranty unknown codes for a synthetic unsupported
accident-free/manufacturer-warranty question. This is a narrow provider check,
not a representative factuality or relevance benchmark.
