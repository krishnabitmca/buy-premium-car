"""Optional derived search index, fenced by PostgreSQL's transactional revision.

Only public inventory enters Elasticsearch. PostgreSQL still calculates evidence
and validates every returned offer in the same snapshot as the revision check.
"""
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from . import inventory_db
from .live_marketplaces import _query_parts, _identity_tokens
from .source_registry_db import _connect, require_database
from .search_timing import measure_call

INDEX = 'carscanner-inventory-v1'
_backend = ContextVar('inventory_search_backend', default='postgresql')
_retry_after = 0.0


class IndexUnavailable(RuntimeError):
    pass


def backend():
    return _backend.get()


def request(method, path, body=None, *, indexer=False, ndjson=False):
    endpoint = os.getenv('CARSCANNER_ELASTICSEARCH_URL', '').rstrip('/')
    key = os.getenv('CARSCANNER_ELASTICSEARCH_INDEXER_API_KEY' if indexer else
                    'CARSCANNER_ELASTICSEARCH_API_KEY', '')
    parsed = urlparse(endpoint)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or not key:
        raise IndexUnavailable('Elasticsearch configuration unavailable')
    data = body.encode() if isinstance(body, str) else json.dumps(body).encode() if body is not None else None
    req = Request(endpoint + '/' + INDEX + path, data=data, method=method,
                  headers={'Authorization': 'ApiKey ' + key,
                           'Content-Type': 'application/x-ndjson' if ndjson else 'application/json'})
    try:
        with urlopen(req, timeout=30 if indexer else 2) as response:
            raw = response.read(16_000_001)
            if len(raw) > 16_000_000:
                raise IndexUnavailable('Elasticsearch response exceeded size limit')
            return json.loads(raw)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        # Never log vendor errors, headers, URLs or credentials.
        raise IndexUnavailable('Elasticsearch request failed') from None


def key_of(row):
    return str(row['vehicle_id']) + ':' + str(row.get('price_basis') or 'unspecified')


def expire_minutes():
    return max(60, int(os.getenv('CARSCANNER_INVENTORY_EXPIRE_MINUTES', '10080')))


def revision(conn):
    return int(conn.execute('select revision from public.search_projection_revision where singleton').fetchone()['revision'])


def search_body(manifest, **kwargs):
    brand, model = _query_parts(kwargs.get('query', ''))
    filters = [{'term': {'kind': 'vehicle'}}, {'term': {'generation': manifest['generation']}}]
    if brand:
        filters.append({'term': {'brand': brand.lower()}})
    tokens = _identity_tokens(model or '')
    if tokens:
        filters.append({'wildcard': {'identity': '* ' + ' '.join(tokens) + ' *'}})
    condition = str(kwargs.get('condition') or 'both').strip().lower()
    if condition in {'used', 'demo'}:
        filters.append({'term': {'condition': condition}})
    if kwargs.get('max_age_years') is not None:
        filters.append({'range': {'year': {'gte': datetime.now(timezone.utc).year - int(kwargs['max_age_years'])}}})
    price = {}
    if kwargs.get('budget_min') is not None:
        price['gte'] = float(kwargs['budget_min'])
    if kwargs.get('budget_max') is not None:
        price['lte'] = float(kwargs['budget_max'])
    offer_filter = {'bool': {'filter': [{'range': {'offers.price': price}}]}} if price else {'match_all': {}}
    filters.append({'nested': {'path': 'offers', 'query': offer_filter}})
    return {'track_total_hits': True, 'from': max(0, min(int(kwargs.get('offset', 0)), 1_000_000)),
            'size': max(1, min(int(kwargs.get('limit', 500)), 2000)), '_source': ['key', 'vehicle_id'],
            'query': {'bool': {'filter': filters}},
            'sort': [{'offers.price': {'order': 'asc', 'mode': 'min', 'nested': {'path': 'offers', 'filter': offer_filter}}},
                     {'observed_at': 'desc'}, {'vehicle_id': 'asc'}, {'price_basis': 'asc'}]}


def search_inventory(*, engine=None, **kwargs):
    global _retry_after
    _backend.set('postgresql')
    use = (engine or os.getenv('CARSCANNER_SEARCH_ENGINE', 'postgresql')) == 'elasticsearch'
    advanced = kwargs.get('with_summary') or any(kwargs.get(k) not in (None, '', (), []) for k in (
        'fuels', 'transmissions', 'body_types', 'max_mileage_km', 'max_owners',
        'manufacture_year', 'seller_city')) or kwargs.get('sort', 'price') != 'price'
    if advanced or not use or kwargs.get('explain') or not inventory_db.enabled() or time.monotonic() < _retry_after:
        return inventory_db.search_inventory(**kwargs)
    try:
        manifest = measure_call('elastic_manifest', request, 'GET', '/_doc/manifest')['_source']
        now = datetime.now(timezone.utc)
        if (manifest['schema'] != 1 or manifest['year'] != now.year or
                manifest['expire_minutes'] != expire_minutes() or
                manifest.get('demo_expire_minutes',1440) != max(60,int(os.getenv('CARSCANNER_DEMO_EXPIRE_MINUTES','1440'))) or
                manifest.get('used_expire_minutes',2880) != max(60,int(os.getenv('CARSCANNER_USED_EXPIRE_MINUTES','2880'))) or
                datetime.fromisoformat(manifest['valid_until']) <= now):
            raise IndexUnavailable('Index freshness policy changed')
        with _connect() as conn:
            conn.execute('set transaction isolation level repeatable read read only')
            if revision(conn) != manifest['revision']:
                raise IndexUnavailable('Index revision behind canonical inventory')
            result = measure_call('elastic_query', request, 'POST', '/_search', search_body(manifest, **kwargs))
            if result.get('timed_out') or result.get('_shards', {}).get('failed', 0):
                raise IndexUnavailable('Incomplete index response')
            hits = result['hits']['hits']
            total_info = result['hits']['total']
            if total_info['relation'] != 'eq':
                raise IndexUnavailable('Index total is not exact')
            ids = [h['_source']['vehicle_id'] for h in hits]
            wanted = [h['_source']['key'] for h in hits]
            if hits:
                hydrate = dict(kwargs, limit=2000, offset=0, return_count=False,
                               _connection=conn, _vehicle_ids=ids)
                rows, _ = inventory_db.search_inventory(**hydrate)
                by_key = {key_of(row): row for row in rows}
                if any(k not in by_key for k in wanted):
                    raise IndexUnavailable('Canonical hydration mismatch')
                rows = [by_key[k] for k in wanted]
            else:
                rows = []
            # Time-based expiry can occur during the network calls without a write.
            if datetime.fromisoformat(manifest['valid_until']) <= datetime.now(timezone.utc):
                raise IndexUnavailable('Index expired during search')
        sources = []
        names = {offer['source'] for row in rows for offer in row['offers']}
        for name in sorted(names):
            sources.append({'name': name, 'status': 'inventory', 'mode': 'inventory',
                            'listings_found': sum(any(o['source'] == name for o in r['offers']) for r in rows)})
        _backend.set('elasticsearch')
        return (rows, sources, int(total_info['value'])) if kwargs.get('return_count') else (rows, sources)
    except (IndexUnavailable, KeyError, TypeError, ValueError):
        _retry_after = time.monotonic() + 5
    except Exception:
        # A missing migration/permission must not take down the working PG path.
        _retry_after = time.monotonic() + 30
    return inventory_db.search_inventory(**kwargs)


def rebuild():
    """Publish only a complete, searchable generation from one DB snapshot.

    A concurrent crawler write advances the fence and causes safe PG fallback.
    The next successful background rebuild makes the new revision searchable.
    """
    require_database()
    mapping = {'mappings': {'dynamic': 'strict', 'properties': {
        'kind': {'type': 'keyword'}, 'generation': {'type': 'keyword'},
        'key': {'type': 'keyword'}, 'vehicle_id': {'type': 'keyword'},
        'brand': {'type': 'keyword'}, 'identity': {'type': 'keyword'},
        'condition': {'type': 'keyword'}, 'year': {'type': 'integer'},
        'price_basis': {'type': 'keyword'}, 'observed_at': {'type': 'date'},
        'offers': {'type': 'nested', 'properties': {'price': {'type': 'double'}}},
        'schema': {'type': 'integer'}, 'revision': {'type': 'long'},
        'expire_minutes': {'type': 'integer'}, 'valid_until': {'type': 'date'},
        'built_at': {'type': 'date'}, 'count': {'type': 'integer'},
    }}}
    # HEAD is read-only and authorized by view_index_metadata; create only once.
    try:
        request('GET', '/_mapping', indexer=True)
    except IndexUnavailable:
        request('PUT', '', mapping, indexer=True)
    generation = uuid4().hex
    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(hours=2)
    count = 0
    with _connect() as conn:
        conn.execute('set transaction isolation level repeatable read read only')
        source_expiry={r['name']:r['expire_after_minutes'] for r in conn.execute('select name,expire_after_minutes from sources')}
        rev = revision(conn)
        offset = 0
        while True:
            rows, _ = inventory_db.search_inventory(limit=500, offset=offset,
                        require_persistence=True, _connection=conn)
            if not rows:
                break
            lines = []
            for row in rows:
                key = key_of(row)
                for offer in row['offers']:
                    from .inventory_freshness import expiry_minutes
                    until = datetime.fromisoformat(offer['last_verified_at'].replace('Z', '+00:00')) + timedelta(
                        minutes=expiry_minutes(row['condition'],source_expiry.get(offer['source'],10080)))
                    valid_until = min(valid_until, until)
                identity = [' ' + ' '.join(_identity_tokens(str(row.get(field) or ''))) + ' '
                            for field in ('model', 'variant', 'listing_name')]
                doc = {'kind': 'vehicle', 'generation': generation, 'key': key,
                       'vehicle_id': str(row['vehicle_id']), 'brand': row['brand'].lower(),
                       'identity': identity, 'condition': row['condition'], 'year': row['mfg_year'],
                       'price_basis': row.get('price_basis') or 'unspecified',
                       'observed_at': row['observed_at'], 'built_at': now.isoformat(),
                       'offers': [{'price': float(o['price_lakh'])} for o in row['offers']]}
                doc_id = generation + '-' + hashlib.sha256(key.encode()).hexdigest()
                lines.extend([json.dumps({'index': {'_id': doc_id}}), json.dumps(doc)])
            result = request('POST', '/_bulk?refresh=wait_for', '\n'.join(lines) + '\n', indexer=True, ndjson=True)
            if result.get('errors'):
                raise IndexUnavailable('Index bulk batch rejected; generation not published')
            count += len(rows)
            offset += len(rows)
            if len(rows) < 500:
                break
            if offset > 1_000_000:
                raise IndexUnavailable('Snapshot exceeds supported pagination')
    if valid_until <= datetime.now(timezone.utc):
        raise IndexUnavailable('Snapshot expired before publication')
    manifest = {'kind': 'manifest', 'schema': 1, 'generation': generation,
                'revision': rev, 'year': now.year, 'expire_minutes': expire_minutes(),
                'demo_expire_minutes':max(60,int(os.getenv('CARSCANNER_DEMO_EXPIRE_MINUTES','1440'))),
                'used_expire_minutes':max(60,int(os.getenv('CARSCANNER_USED_EXPIRE_MINUTES','2880'))),
                'valid_until': valid_until.isoformat(), 'built_at': now.isoformat(), 'count': count}
    request('PUT', '/_doc/manifest?refresh=wait_for', manifest, indexer=True)
    # Keep generations for ten minutes so in-flight readers can finish safely.
    request('POST', '/_delete_by_query?conflicts=proceed', {'query': {'bool': {'filter': [
        {'term': {'kind': 'vehicle'}}, {'range': {'built_at': {'lt': (now - timedelta(minutes=10)).isoformat()}}}
    ], 'must_not': [{'term': {'generation': generation}}]}}}, indexer=True)
    return {'ok': True, 'generation': generation, 'revision': rev, 'count': count,
            'valid_until': valid_until.isoformat()}


if __name__ == '__main__':
    try:
        print(json.dumps(rebuild()))
    except Exception:
        raise SystemExit('Elasticsearch rebuild failed; canonical PostgreSQL search remains available.') from None
