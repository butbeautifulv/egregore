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

    async def aallow(self, key: str) -> bool:
        return self.allow(key)

    async def acheck(self, key: str) -> None:
        if not await self.aallow(key):
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
        self._async_redis = None
        self._async_redis_unavailable = False
        self._redis_url = redis_url or settings.redis_url
        try:
            import redis

            self._redis = redis.from_url(self._redis_url, decode_responses=True)
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

    async def _get_async_redis(self):
        if self._async_redis_unavailable:
            return None
        if self._async_redis is not None:
            return self._async_redis
        try:
            import redis.asyncio as aioredis

            self._async_redis = aioredis.from_url(self._redis_url, decode_responses=True)
            await self._async_redis.ping()
            return self._async_redis
        except Exception:
            self._async_redis = None
            self._async_redis_unavailable = True
            return None

    async def aallow(self, key: str) -> bool:
        redis_client = await self._get_async_redis()
        if redis_client is None:
            return await self._fallback.aallow(key)
        now = int(time.time())
        pipe = redis_client.pipeline()
        bucket_key = f"cys:rate:{key}"
        pipe.zremrangebyscore(bucket_key, 0, now - self.window_seconds)
        pipe.zadd(bucket_key, {str(now): now})
        pipe.zcard(bucket_key)
        pipe.expire(bucket_key, self.window_seconds + 1)
        _, _, count, _ = await pipe.execute()
        return count <= self.max_calls

    async def acheck(self, key: str) -> None:
        if not await self.aallow(key):
            raise RateLimitExceeded(f"Rate limit exceeded for key: {key}")
