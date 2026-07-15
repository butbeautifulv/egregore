from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from cys_core.infrastructure.redis_leader import redis_leader


class _FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}

    def ping(self) -> bool:
        return True

    def set(self, key: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool | None:
        del ex
        if nx and key in self.kv:
            return None
        self.kv[key] = value
        return True

    def get(self, key: str) -> str | None:
        return self.kv.get(key)

    def eval(self, _script: str, _numkeys: int, key: str, token: str) -> int:
        if self.kv.get(key) == token:
            del self.kv[key]
            return 1
        return 0


def _connect_factory(fake: _FakeRedis) -> Callable[[str], Any]:
    def _connect(_url: str) -> _FakeRedis:
        return fake

    return _connect


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_leader_holds_and_releases(monkeypatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(
        "cys_core.infrastructure.redis_leader.ResilientRedisClient._default_connect",
        staticmethod(_connect_factory(fake)),
    )

    async with redis_leader("eg:test", ttl=30, redis_url="redis://fake") as is_leader:
        assert is_leader is True
        assert fake.kv["eg:test"]

    assert "eg:test" not in fake.kv


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_leader_skips_when_locked(monkeypatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(
        "cys_core.infrastructure.redis_leader.ResilientRedisClient._default_connect",
        staticmethod(_connect_factory(fake)),
    )

    fake.kv["eg:test"] = "other-token"

    async with redis_leader("eg:test", ttl=30, redis_url="redis://fake") as is_leader:
        assert is_leader is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_leader_skips_when_redis_unavailable(monkeypatch) -> None:
    def _fail(_url: str) -> Any:
        raise ConnectionError("down")

    monkeypatch.setattr(
        "cys_core.infrastructure.redis_leader.ResilientRedisClient._default_connect",
        staticmethod(_fail),
    )

    async with redis_leader("eg:test", ttl=30, redis_url="redis://fake") as is_leader:
        assert is_leader is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_leader_only_one_holder(monkeypatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(
        "cys_core.infrastructure.redis_leader.ResilientRedisClient._default_connect",
        staticmethod(_connect_factory(fake)),
    )

    results: list[bool] = []

    async def _try() -> None:
        async with redis_leader("eg:test", ttl=30, redis_url="redis://fake") as is_leader:
            results.append(is_leader)
            if is_leader:
                await asyncio.sleep(0.05)

    await asyncio.gather(_try(), _try())
    assert results.count(True) == 1
    assert results.count(False) == 1
