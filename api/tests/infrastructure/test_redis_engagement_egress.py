from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import pytest

from cys_core.infrastructure.engagement.redis_egress import RedisEngagementEgress


class _FakePubSub:
    def __init__(self, redis: "_FakeRedis", *, ignore_subscribe_messages: bool = True) -> None:
        self._redis = redis
        self._ignore_subscribe = ignore_subscribe_messages
        self._channels: list[str] = []
        self._queue: deque[dict[str, Any]] = deque()

    def subscribe(self, channel: str) -> None:
        self._channels.append(channel)
        self._redis._pubsubs.setdefault(channel, []).append(self)

    def unsubscribe(self, channel: str) -> None:
        subs = self._redis._pubsubs.get(channel, [])
        self._redis._pubsubs[channel] = [s for s in subs if s is not self]
        self._channels = [c for c in self._channels if c != channel]

    def close(self) -> None:
        for channel in list(self._channels):
            self.unsubscribe(channel)

    def get_message(self, timeout: float = 1.0):
        if self._queue:
            return self._queue.popleft()
        return None

    def _push(self, message: dict[str, Any]) -> None:
        self._queue.append(message)


class _FakeRedis:
    def __init__(self) -> None:
        self.lists: dict[str, deque[str]] = defaultdict(deque)
        self._pubsubs: dict[str, list[_FakePubSub]] = defaultdict(list)

    def ping(self) -> bool:
        return True

    def rpush(self, key: str, value: str) -> int:
        self.lists[key].append(value)
        return len(self.lists[key])

    def ltrim(self, key: str, start: int, end: int) -> None:
        items = list(self.lists[key])
        self.lists[key] = deque(items[start : end + 1 if end >= 0 else None])

    def expire(self, key: str, ttl: int) -> bool:
        return True

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = list(self.lists.get(key, []))
        if end == -1:
            end = len(items) - 1
        return items[start : end + 1]

    def publish(self, channel: str, message: str) -> int:
        count = 0
        for sub in self._pubsubs.get(channel, []):
            sub._push({"type": "message", "channel": channel, "data": message})
            count += 1
        return count

    def pubsub(self, *, ignore_subscribe_messages: bool = True) -> _FakePubSub:
        return _FakePubSub(self, ignore_subscribe_messages=ignore_subscribe_messages)


@pytest.mark.unit
def test_redis_egress_publish_visible_across_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr("redis.Redis.from_url", lambda *_args, **_kwargs: fake)
    writer = RedisEngagementEgress(redis_url="redis://localhost:6379/0")
    reader = RedisEngagementEgress(redis_url="redis://localhost:6379/0")
    assert writer.active_backend == "redis"

    writer.publish_status(
        "eng-1",
        "job_finished",
        {"tenant_id": "default", "persona": "consultant", "job_id": "job-1"},
    )
    events = reader.snapshot("eng-1", tenant_id="default")
    assert len(events) == 1
    assert events[0]["phase"] == "job_finished"
    assert events[0]["payload"]["persona"] == "consultant"


@pytest.mark.unit
def test_redis_egress_falls_back_to_memory_when_redis_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "redis.Redis.from_url",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("down")),
    )
    egress = RedisEngagementEgress(redis_url="redis://invalid:1/0")
    assert egress.active_backend == "memory"
    egress.publish_event("eng-2", "job_finished", {"tenant_id": "default"})
    events = egress.snapshot("eng-2", tenant_id="default")
    assert len(events) == 1
    assert events[0]["type"] == "job_finished"
