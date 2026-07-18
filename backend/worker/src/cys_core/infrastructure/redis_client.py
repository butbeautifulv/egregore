from __future__ import annotations

import random
import time
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_MAX_RETRIES = 1


class ResilientRedisClient:
    """Lazy Redis connection with ping validation, retry-with-backoff, and optional strict mode.

    ensure_connected() used to try exactly once and give up (or raise, if strict) on any
    failure — a Redis restart or brief network blip failed the very next call outright, same
    gap Postgres had before docs/MICROSERVICES_SPLIT_PLAN.md §24.4 point 4/§32 closed it there.
    """

    def __init__(
        self,
        redis_url: str,
        *,
        connect: Callable[[str], Any] | None = None,
        strict: bool = False,
        unavailable_error: str = "redis_unavailable",
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self._redis_url = redis_url
        self._connect = connect or self._default_connect
        self._strict = strict
        self._unavailable_error = unavailable_error
        self._max_retries = max_retries
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
        attempt = 0
        while True:
            try:
                self._redis = self._connect(self._redis_url)
                return True
            except Exception as exc:
                if attempt >= self._max_retries:
                    self._redis = None
                    if self._strict:
                        raise RuntimeError(self._unavailable_error) from exc
                    return False
                delay = min(4.0, 0.25 * (2**attempt)) * (1.0 + random.random())
                logger.warning(
                    "redis_connect_retrying",
                    attempt=attempt + 1,
                    max_retries=self._max_retries,
                    delay_s=round(delay, 2),
                    error=str(exc),
                )
                time.sleep(delay)
                attempt += 1

    @property
    def client(self) -> Any:
        if not self.ensure_connected():
            raise RuntimeError(self._unavailable_error)
        return self._redis
