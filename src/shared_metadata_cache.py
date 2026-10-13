"""Optional shared source metadata cache. Inventory and user data never enter it."""
import hashlib
import json
import os
import threading
import time
from urllib.parse import urlsplit

_lock = threading.Lock()
_client = None
_url = None
_retry_after = 0
MAX_BYTES = 512_000


def configured():
    return bool(os.getenv('CARSCANNER_REDIS_URL'))


def cache_key(identity):
    digest = hashlib.sha256(json.dumps(identity, default=str).encode()).hexdigest()
    return 'carscanner:source-registry:v1:' + digest


def _connection():
    global _client, _url, _retry_after
    url = os.getenv('CARSCANNER_REDIS_URL')
    if not url:
        return None
    with _lock:
        if url != _url:
            if _client is not None:
                _client.close()
            _client, _url, _retry_after = None, url, 0
        if time.monotonic() < _retry_after:
            return None
        if _client is None:
            from redis import Redis
            from redis.backoff import NoBackoff
            from redis.retry import Retry
            parts = urlsplit(url)
            if parts.scheme not in {'redis', 'rediss'} or parts.query:
                raise ValueError('Use a Redis connection URL without query overrides')
            _client = Redis.from_url(url, socket_connect_timeout=0.15,
                socket_timeout=0.15, retry=Retry(NoBackoff(), 0), max_connections=8,
                decode_responses=True, protocol=2)
        return _client


def _failed():
    global _retry_after
    with _lock:
        _retry_after = time.monotonic() + 30


def get(identity):
    try:
        client = _connection()
        if client is None:
            return None
        # Read value and remaining life in one transaction. L1 must not renew
        # an entry's original metadata freshness window after a shared hit.
        with client.pipeline(transaction=True) as pipe:
            raw, remaining_ms = pipe.get(cache_key(identity)).pttl(cache_key(identity)).execute()
        if raw is None or remaining_ms <= 0 or len(raw.encode()) > MAX_BYTES:
            return None
        rows = json.loads(raw)
        if not isinstance(rows, list) or not all(isinstance(row, dict) and row.get('name') for row in rows):
            return None
        return rows, min(remaining_ms / 1000, 15)
    except json.JSONDecodeError:
        return None
    except Exception:
        # No exception text: client errors can contain authentication details.
        _failed()
        return None


def put(identity, rows, ttl):
    try:
        if ttl <= 0:
            return
        raw = json.dumps(rows, ensure_ascii=False, allow_nan=False)
        if len(raw.encode()) > MAX_BYTES:
            return
        client = _connection()
        if client is not None:
            client.set(cache_key(identity), raw, px=max(1, int(min(ttl, 15) * 1000)))
    except Exception:
        _failed()
