"""Session cache backed by Redis when available."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

try:
    import redis  # type: ignore
except ImportError:  # pragma: no cover - redis optional
    redis = None

from .config import settings


class SessionCache:
    def __init__(self, ttl_seconds: int = 60) -> None:
        self.ttl = ttl_seconds
        self._memory: Dict[str, tuple[float, str]] = {}
        if settings.redis_url and redis:
            self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        else:
            self.client = None

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        if self.client:
            payload = self.client.get(self._session_key(key))
            return json.loads(payload) if payload else None
        entry = self._memory.get(key)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at < time.time():
            self._memory.pop(key, None)
            return None
        return json.loads(payload)

    def set(self, key: str, value: Dict[str, Any]) -> None:
        serialized = json.dumps(value)
        if self.client:
            self.client.setex(self._session_key(key), self.ttl, serialized)
        else:
            self._memory[key] = (time.time() + self.ttl, serialized)

    def invalidate(self, key: str) -> None:
        if self.client:
            self.client.delete(self._session_key(key))
        else:
            self._memory.pop(key, None)

    @staticmethod
    def _session_key(key: str) -> str:
        return f"session:{key}"


session_cache = SessionCache()
