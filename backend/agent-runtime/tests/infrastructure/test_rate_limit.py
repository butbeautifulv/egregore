from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limiters_memory_and_redis(monkeypatch):
    from cys_core.security import rate_limit

    times = iter([100.0, 101.0, 200.0])
    monkeypatch.setattr(rate_limit.time, "time", lambda: next(times))
    limiter = rate_limit.InMemoryRateLimiter(max_calls=1, window_seconds=10)
    assert limiter.allow("key") is True
    assert limiter.allow("key") is False
    assert limiter.allow("key") is True
    monkeypatch.setattr(rate_limit.time, "time", lambda: 250.0)
    assert await rate_limit.InMemoryRateLimiter(max_calls=1).aallow("async-key") is True
    with pytest.raises(rate_limit.RateLimitExceeded, match="Rate limit exceeded"):
        await rate_limit.InMemoryRateLimiter(max_calls=0).acheck("async-blocked")
    monkeypatch.setattr(rate_limit.time, "time", lambda: 300.0)
    with pytest.raises(rate_limit.RateLimitExceeded, match="Rate limit exceeded"):
        rate_limit.InMemoryRateLimiter(max_calls=0).check("blocked")

    class FakePipeline:
        def __init__(self, count):
            self.count = count
            self.calls = []

        def zremrangebyscore(self, *args):
            self.calls.append(("zremrangebyscore", args))

        def zadd(self, *args):
            self.calls.append(("zadd", args))

        def zcard(self, *args):
            self.calls.append(("zcard", args))

        def expire(self, *args):
            self.calls.append(("expire", args))

        def execute(self):
            return [None, None, self.count, None]

    class FakeRedis:
        def __init__(self, count):
            self.count = count

        def ping(self):
            return True

        def pipeline(self):
            return FakePipeline(self.count)

    module = types.ModuleType("redis")
    module.from_url = lambda *_args, **_kwargs: FakeRedis(1)
    monkeypatch.setitem(sys.modules, "redis", module)
    redis_limiter = rate_limit.RedisRateLimiter(max_calls=1, window_seconds=10, redis_url="redis://unit")
    assert redis_limiter.allow("key") is True

    redis_limiter._redis = FakeRedis(2)
    assert redis_limiter.allow("key") is False
    with pytest.raises(rate_limit.RateLimitExceeded):
        redis_limiter.check("key")
    redis_limiter._redis = None
    assert redis_limiter.allow("fallback-key") is True

    class FakeAsyncPipeline:
        def __init__(self, count):
            self.count = count

        def zremrangebyscore(self, *args):
            return None

        def zadd(self, *args):
            return None

        def zcard(self, *args):
            return None

        def expire(self, *args):
            return None

        async def execute(self):
            return [None, None, self.count, None]

    class FakeAsyncRedis:
        def __init__(self, count):
            self.count = count

        async def ping(self):
            return True

        def pipeline(self):
            return FakeAsyncPipeline(self.count)

    redis_pkg = types.ModuleType("redis")
    redis_pkg.__path__ = []
    redis_pkg.from_url = lambda *_args, **_kwargs: FakeRedis(1)
    async_module = types.ModuleType("redis.asyncio")
    async_module.from_url = lambda *_args, **_kwargs: FakeAsyncRedis(1)
    monkeypatch.setitem(sys.modules, "redis", redis_pkg)
    monkeypatch.setitem(sys.modules, "redis.asyncio", async_module)
    async_limiter = rate_limit.RedisRateLimiter(max_calls=1, window_seconds=10, redis_url="redis://unit")
    assert await async_limiter.aallow("async-key") is True
    assert await async_limiter._get_async_redis() is async_limiter._async_redis

    async_limiter._async_redis = FakeAsyncRedis(2)
    assert await async_limiter.aallow("async-key") is False
    with pytest.raises(rate_limit.RateLimitExceeded):
        await async_limiter.acheck("async-key")

    closed = AsyncMock()
    async_limiter._async_redis = closed
    await async_limiter.aclose()
    closed.aclose.assert_awaited_once()
    assert async_limiter._async_redis is None

    async_module.from_url = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("redis down"))
    fallback_async = rate_limit.RedisRateLimiter(max_calls=1, window_seconds=10, redis_url="redis://unit")
    fallback_async._async_redis = None
    fallback_async._async_redis_unavailable = False
    assert await fallback_async.aallow("fallback-async") is True
    assert await fallback_async._get_async_redis() is None
