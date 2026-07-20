"""Abuse case: recursive tool abuse — rate limits stop runaway loops."""

import pytest

from cys_core.security.rate_limit import InMemoryRateLimiter, RateLimitExceeded


def test_rate_limit_blocks_excessive_calls():
    limiter = InMemoryRateLimiter(max_calls=5, window_seconds=60)
    for _ in range(5):
        assert limiter.allow("session-1:parse_netflow")
    with pytest.raises(RateLimitExceeded):
        limiter.check("session-1:parse_netflow")
