"""Distributed leader election via Redis SET NX."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog

from cys_core.infrastructure.redis_client import ResilientRedisClient

logger = structlog.get_logger(__name__)

_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


@asynccontextmanager
async def redis_leader(
    key: str,
    *,
    ttl: int,
    redis_url: str,
) -> AsyncIterator[bool]:
    """Try to acquire a Redis leader lock. Yields True if leader, False if skipped."""
    client_wrapper = ResilientRedisClient(redis_url)
    if not client_wrapper.ensure_connected():
        logger.warning("redis_leader_skip_unavailable", key=key)
        yield False
        return

    token = str(uuid.uuid4())
    redis = client_wrapper.client
    acquired = await asyncio.to_thread(redis.set, key, token, nx=True, ex=ttl)
    if not acquired:
        yield False
        return

    try:
        yield True
    finally:
        try:
            await asyncio.to_thread(redis.eval, _RELEASE_LUA, 1, key, token)
        except Exception:
            logger.warning("redis_leader_release_failed", key=key)
