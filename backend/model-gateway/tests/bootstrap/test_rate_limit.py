from __future__ import annotations

import pytest

from bootstrap.rate_limit import RateLimitExceeded, RedisSlidingWindowRateLimiter


class _Pipeline:
    def __init__(self, count: int) -> None:
        self.count = count

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def zremrangebyscore(self, *_args):
        return self

    def zadd(self, *_args):
        return self

    def zcard(self, *_args):
        return self

    def expire(self, *_args):
        return self

    async def execute(self):
        return (0, 1, self.count, True)


class _Redis:
    def __init__(self, count: int) -> None:
        self.count = count

    def pipeline(self, *, transaction: bool):
        assert transaction is True
        return _Pipeline(self.count)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_sliding_window_allows_then_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = RedisSlidingWindowRateLimiter(redis_url="redis://unit", max_calls=1, window_seconds=60)
    monkeypatch.setattr(limiter, "_get_client", lambda: _async_value(_Redis(1)))
    await limiter.check("persona:session")
    monkeypatch.setattr(limiter, "_get_client", lambda: _async_value(_Redis(2)))
    with pytest.raises(RateLimitExceeded):
        await limiter.check("persona:session")


async def _async_value(value):
    return value
