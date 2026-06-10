from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from config import settings


class RateLimitExceeded(Exception):
    """Raised when agent exceeds rate limits (DoW protection)."""


class InMemoryRateLimiter:
    """Fallback rate limiter when Redis is unavailable."""

    def __init__(self, max_calls: int, window_seconds: int = 60) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._buckets: dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        bucket = self._buckets[key]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_calls:
            return False
        bucket.append(now)
        return True

    def check(self, key: str) -> None:
        if not self.allow(key):
            raise RateLimitExceeded(f"Rate limit exceeded for key: {key}")


class RedisRateLimiter:
    """Redis-backed sliding window rate limiter."""

    def __init__(
        self,
        max_calls: int | None = None,
        window_seconds: int = 60,
        redis_url: str | None = None,
    ) -> None:
        self.max_calls = max_calls or settings.max_tool_calls_per_minute
        self.window_seconds = window_seconds
        self._fallback = InMemoryRateLimiter(self.max_calls, window_seconds)
        self._redis = None
        try:
            import redis

            self._redis = redis.from_url(redis_url or settings.redis_url, decode_responses=True)
            self._redis.ping()
        except Exception:
            self._redis = None

    def allow(self, key: str) -> bool:
        if self._redis is None:
            return self._fallback.allow(key)
        now = int(time.time())
        pipe = self._redis.pipeline()
        bucket_key = f"cys:rate:{key}"
        pipe.zremrangebyscore(bucket_key, 0, now - self.window_seconds)
        pipe.zadd(bucket_key, {str(now): now})
        pipe.zcard(bucket_key)
        pipe.expire(bucket_key, self.window_seconds + 1)
        _, _, count, _ = pipe.execute()
        return count <= self.max_calls

    def check(self, key: str) -> None:
        if not self.allow(key):
            raise RateLimitExceeded(f"Rate limit exceeded for key: {key}")
