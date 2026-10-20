# ADR 032 — Demo discovery intent is not condition evidence

Status: implemented locally; operational discovery measurement pending.

Search queries express the inventory gap CarScanner wants to investigate. They do
not describe the page returned by a search engine. The previous classifier mixed
query text into candidate evidence, so any ordinary dealer directory or used-car
page returned for a demo query could be stored with condition `demo`.

Condition classification now uses only the result title, snippet and normalized
URL path. Explicit demo/demonstrator terms remain candidate evidence; explicit
used/pre-owned terms remain used evidence; ambiguous results stay `both`. Source
type classification follows the same returned-page evidence boundary. The query is
retained as provenance but contributes neither condition nor confidence.

This is a discovery-quality control, not inventory validation. Search snippets can
be stale or inaccurate. A candidate still needs a bounded worker-environment probe,
vehicle-level condition, current availability, asking price, original URL and a
reviewed parser/API before activation. Existing discovery rows can be corrected by
normal rediscovery through the existing upsert; this decision performs no bulk
database rewrite, source activation or inventory ingestion.
