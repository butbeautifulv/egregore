from __future__ import annotations

import time
from typing import Any

import structlog

from cys_core.infrastructure.redis_client import ResilientRedisClient

logger = structlog.get_logger(__name__)


class BusDedupStore:
    """Shared bus ingress dedup — Redis when available, in-process fallback."""

    KEY_PREFIX = "cys:bus:dedup:"

    def __init__(
        self,
        *,
        redis_url: str,
        ttl_seconds: int = 300,
        strict_redis: bool = False,
    ) -> None:
        self._ttl = ttl_seconds
        self._strict_redis = strict_redis
        self._memory: dict[str, float] = {}
        self._redis = ResilientRedisClient(
            redis_url,
            strict=strict_redis,
            unavailable_error="bus_dedup_redis_unavailable",
        )

    def _purge_expired_memory(self, now: float) -> None:
        expired = [key for key, ts in self._memory.items() if now - ts > self._ttl]
        for key in expired:
            del self._memory[key]

    def is_duplicate(self, fingerprint: str) -> bool:
        if not fingerprint:
            return False
        if self._redis.ensure_connected():
            try:
                key = f"{self.KEY_PREFIX}{fingerprint}"
                inserted = self._redis.client.set(key, "1", nx=True, ex=self._ttl)
                return not bool(inserted)
            except Exception as exc:
                logger.warning("bus_dedup_redis_failed", error=str(exc))
                self._redis.invalidate()
                if self._strict_redis:
                    raise RuntimeError("bus_dedup_redis_unavailable") from exc
        now = time.time()
        self._purge_expired_memory(now)
        if fingerprint in self._memory:
            return True
        self._memory[fingerprint] = now
        return False


_dedup_store: BusDedupStore | None = None


def get_bus_dedup_store(*, redis_url: str, strict_redis: bool = False, ttl_seconds: int = 300) -> BusDedupStore:
    global _dedup_store
    if _dedup_store is None:
        _dedup_store = BusDedupStore(redis_url=redis_url, strict_redis=strict_redis, ttl_seconds=ttl_seconds)
    return _dedup_store


def reset_bus_dedup_store() -> None:
    global _dedup_store
    _dedup_store = None
