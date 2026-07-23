from __future__ import annotations

import time
from uuid import uuid4


class RateLimitExceeded(Exception):
    """The configured shared rate window has no remaining capacity."""


class RateLimiterUnavailable(Exception):
    """Redis cannot enforce a limiter configured as a security boundary."""


class RedisSlidingWindowRateLimiter:
    def __init__(self, *, redis_url: str, max_calls: int, window_seconds: int) -> None:
        self._redis_url = redis_url
        self._max_calls = max_calls
        self._window_seconds = window_seconds
        self._client = None

    async def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import redis.asyncio as redis

            client = redis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
            self._client = client
            return client
        except Exception as exc:
            raise RateLimiterUnavailable("Model Gateway rate limiter is unavailable") from exc

    async def check(self, key: str) -> None:
        client = await self._get_client()
        now = time.time()
        bucket = f"egregore:model-gateway:rate:{key}"
        # A unique member prevents same-second calls from overwriting each other.
        async with client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(bucket, 0, now - self._window_seconds)
            pipe.zadd(bucket, {f"{now}:{uuid4().hex}": now})
            pipe.zcard(bucket)
            pipe.expire(bucket, self._window_seconds + 1)
            _removed, _added, count, _expiry = await pipe.execute()
        if int(count) > self._max_calls:
            raise RateLimitExceeded(f"Model Gateway rate limit exceeded for key: {key}")

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
