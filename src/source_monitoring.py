"""Explicit registry monitoring alongside open-web source discovery."""
from urllib.parse import urlsplit
from datetime import datetime, timedelta, timezone
from .discovery import DiscoveryResult


def inventory_urls(source):
    if source.get('enabled', True) is False:
        return []
    urls = [source.get('url')]
    urls.extend(e.get('url') for e in source.get('endpoints', []) if e.get('is_active', True))
    return list(dict.fromkeys(u.strip() for u in urls if isinstance(u, str) and urlsplit(u).scheme in {'http', 'https'}))


def crawl_queue(registry):
    queue, seen = [], set()
    for source in registry:
        for url in inventory_urls(source):
            if url in seen:
                continue
            seen.add(url)
            queue.append((source['name'], url, int(source.get('tier', 2))))
    return queue


def registered_candidates(registry):
    candidates, seen = [], set()
    live_urls = {url for source in registry if source.get('adapter_status') == 'live' for url in inventory_urls(source)}
    for source in registry:
        if source.get('adapter_status') == 'live':
            continue
        brands = source.get('brands') or []
        conditions = source.get('conditions') or []
        for url in inventory_urls(source):
            if url in seen or url in live_urls:
                continue
            seen.add(url)
            candidates.append(DiscoveryResult(
                url=url, title=source['name'], snippet='Registered source requiring inventory validation',
                domain=urlsplit(url).netloc.lower().removeprefix('www.'), query='registry_monitoring',
                source_type=source.get('source_type', 'unknown'),
                condition=conditions[0] if len(conditions) == 1 else 'both',
                segment=(source.get('segments') or ['premium'])[0],
                brand_hint=brands[0] if len(brands) == 1 and brands[0] != 'all' else None,
                candidate_confidence=1.0,
            ))
    return candidates


def merge_candidates(registered, discovered, min_confidence, limit):
    out, seen = [], set()
    for item in [*registered, *discovered]:
        if item.url in seen or item.candidate_confidence < min_confidence:
            continue
        seen.add(item.url)
        out.append(item)
    return out[:max(0, limit)]


def plan_probes(registered, discovered, history, min_confidence, limit, *, now=None):
    """Reserve one in five slots for web discoveries, then lend idle slots.

    Oldest attempted candidates come first within each pool. Unattempted
    candidates precede retries. Staged adapters await review rather than
    repeatedly consuming discovery capacity.
    """
    now = now or datetime.now(timezone.utc)
    registered = merge_candidates(registered, [], min_confidence, len(registered))
    known = {item.url for item in registered}
    discovered = [item for item in merge_candidates([], discovered, min_confidence, len(discovered))
                  if item.url not in known]
    def ready(item):
        previous = history.get(item.url, {})
        if previous.get('status') in {'validated','promoted'}:
            return False
        attempted = previous.get('last_probe_at')
        running = (previous.get('probe_result') or {}).get('status') == 'running'
        return not (running and attempted and attempted > now - timedelta(minutes=30))
    def order(item):
        stamp = history.get(item.url, {}).get('last_probe_at')
        return (stamp is not None, stamp or datetime.min.replace(tzinfo=timezone.utc), item.url)
    pools = [sorted((item for item in pool if ready(item)), key=order)
             for pool in (registered, discovered)]
    selected = []
    for slot in range(max(0, min(int(limit), 100))):
        preferred = 1 if slot % 5 == 0 else 0
        pool = pools[preferred] or pools[1-preferred]
        if not pool:
            break
        selected.append(pool.pop(0))
    return selected
