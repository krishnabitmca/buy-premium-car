# Volkswagen Certified Pre-Owned source endpoint — reviewed rollout

## Evidence (28 October 2026)

The daily acquisition workflow (run 40659127810) logged a hostname-mismatch
TLS certificate verification failure when fetching
`https://www.dasweltauto.co.in/buy-used-cars`.

Volkswagen India's Certified Pre-Owned page links its **Buy** action to
`www.vwcertifiedpreowned.co.in`:
`https://www.volkswagen.co.in/en/available-used-cars/vwcertified-pre-owned-vehicles.html`.
The corresponding inventory page is
`https://www.vwcertifiedpreowned.co.in/buy-used-cars`.

## Scope and safety

This PR updates **only the YAML bootstrap/fallback URL** and a deterministic
configuration test. It does **not** update the canonical PostgreSQL source
registry, disable TLS verification, retry through an untrusted host, modify
existing vehicle observations, or mark inaccessible inventory as sold.

The production source row `das_weltauto` currently uses the previous URL.
The runtime loads the database registry when available, and ordinary
`sync_registry` intentionally preserves existing URLs. **Merging this PR
alone will not fix production acquisition.**

## Review and deployment gate

1. From the same environment/network as the acquisition worker, validate the
   new host's DNS, TLS hostname, HTTP status, robots/access policy, and actual
   listing-card extraction. Do not disable TLS validation or evade 403/429.
2. Compare a bounded sample of parsed listings against visible OEM inventory;
   check identity, location, seller URL, condition, image URLs and pagination.
3. After independent approval, perform a **single-source**, compare-and-swap
   update of `public.sources.url` for source_key `das_weltauto`, only when
   its existing URL matches the old URL. Review its `source_endpoints` and
   deactivate the obsolete endpoint only if validated; do not use a bulk
   reviewed-update sync or change emergency source disables.
4. Run one bounded source acquisition, verify committed/eligible listing counts
   and source-health telemetry, and confirm there is no false-absence
   reconciliation on failure. Roll back the URL if extraction regresses.

The observed failure may be specific to the GitHub runner's network. No
production registry change is authorized by this PR.
