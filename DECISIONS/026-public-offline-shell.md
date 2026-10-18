# 026: PWA-first mobile shell without offline inventory

Choose a progressive web application as the first mobile packaging increment,
sharing existing web/backend rules. Add a standalone manifest, explicit 192/512
icons, theme/touch icon metadata and a service worker on HTTPS/loopback. Native
apps, app-store distribution and real-device installation/accessibility acceptance
remain separate gates. Browser install promotion is platform dependent; no push
permission or automatic installation is requested.

Cache an exact allowlist of public static shell files only: index, buyer script,
manifest and app icons. Always bypass `/api/`, mutations and third-party media.
Do not cache prices, source/availability responses, accounts, watches or AI output.
Root/index navigation and allowed static files use the network when available,
refresh their public cache and use shell fallback on a network failure. Honor
private/no-store responses. A failed cache write must not replace a successful
network response. Future authenticated HTML must never enter this shell contract.

Offline cold reload can display the interface and device-saved choice labels,
with an explicit offline warning. It cannot present stored prices as current or
execute search/revalidation without a network. Reconnect refreshes catalogue
metadata and rechecks saved offers; ordinary searches remain buyer initiated.

Serve only explicit public assets with known MIME types and revalidation headers;
do not broaden directory serving. Docker copies those assets. Worker activation
cleans only this app's older shell caches, preserving unrelated storage, and
does not force replacement of an active version. Cache schema changes require a
worker/cache version change. Public assets refresh online under the same version.

Verify actual Chromium service-worker activation, offline reload, saved criteria,
absence of API cache entries and fresh search after reconnect. Unit contracts
also check API/media/mutation bypass, private response exclusion and cache-quota
failure. This does not close all mobile or national availability requirements.

References:
- https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers
- https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable
