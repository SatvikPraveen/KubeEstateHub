"""Read-through response cache with O(1) invalidation.

Keys embed a *generation* number; writes bump the generation (``INCR``) instead of
scanning and deleting keys, so invalidation cost does not grow with cache size and old
entries simply expire. When Redis is unavailable the cache degrades to a no-op.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from prometheus_client import Counter

log = logging.getLogger(__name__)
CACHE_EVENTS = Counter("listings_cache_events_total", "Cache lookups by outcome", ["outcome"])
GENERATION_KEY = "listings:generation"


class ResponseCache:
    def __init__(self, client: Any | None, ttl_seconds: int) -> None:
        self._client = client
        self._ttl = ttl_seconds

    @classmethod
    def from_url(cls, url: str, ttl_seconds: int) -> ResponseCache:
        if not url:
            return cls(None, ttl_seconds)
        import redis

        client = redis.Redis.from_url(url, socket_timeout=0.25, socket_connect_timeout=0.25)
        return cls(client, ttl_seconds)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _generation(self) -> int:
        raw = self._client.get(GENERATION_KEY)
        return int(raw) if raw else 0

    def key(self, namespace: str, params: dict[str, Any]) -> str | None:
        if not self._client:
            return None
        try:
            digest = hashlib.sha256(
                json.dumps(params, sort_keys=True, default=str).encode()
            ).hexdigest()[:24]
            return f"listings:v{self._generation()}:{namespace}:{digest}"
        except Exception as exc:
            log.warning("cache unavailable: %s", exc)
            return None

    def get(self, key: str | None) -> Any | None:
        if not key:
            return None
        try:
            raw = self._client.get(key)
        except Exception as exc:
            log.warning("cache read failed: %s", exc)
            CACHE_EVENTS.labels("error").inc()
            return None
        CACHE_EVENTS.labels("hit" if raw is not None else "miss").inc()
        return json.loads(raw) if raw is not None else None

    def set(self, key: str | None, value: Any) -> None:
        if not key:
            return
        try:
            self._client.setex(key, self._ttl, json.dumps(value, default=str))
        except Exception as exc:
            log.warning("cache write failed: %s", exc)

    def invalidate(self) -> None:
        if not self._client:
            return
        try:
            self._client.incr(GENERATION_KEY)
        except Exception as exc:
            log.warning("cache invalidation failed: %s", exc)

    def ping(self) -> bool:
        if not self._client:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False
