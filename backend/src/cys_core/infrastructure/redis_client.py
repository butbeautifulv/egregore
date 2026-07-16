from __future__ import annotations

from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


class ResilientRedisClient:
    """Lazy Redis connection with ping validation and optional strict mode."""

    def __init__(
        self,
        redis_url: str,
        *,
        connect: Callable[[str], Any] | None = None,
        strict: bool = False,
        unavailable_error: str = "redis_unavailable",
    ) -> None:
        self._redis_url = redis_url
        self._connect = connect or self._default_connect
        self._strict = strict
        self._unavailable_error = unavailable_error
        self._redis: Any = None

    @staticmethod
    def _default_connect(redis_url: str) -> Any:
        import redis

        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client

    def invalidate(self) -> None:
        self._redis = None

    def ensure_connected(self) -> bool:
        if self._redis is not None:
            try:
                self._redis.ping()
                return True
            except Exception:
                self._redis = None
        try:
            self._redis = self._connect(self._redis_url)
            return True
        except Exception as exc:
            self._redis = None
            if self._strict:
                raise RuntimeError(self._unavailable_error) from exc
            return False

    @property
    def client(self) -> Any:
        if not self.ensure_connected():
            raise RuntimeError(self._unavailable_error)
        return self._redis
