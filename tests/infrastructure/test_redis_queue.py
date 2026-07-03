from __future__ import annotations

import json
from collections import deque

import pytest

from cys_core.infrastructure.queue import InMemoryJobQueue, RedisJobQueue


class _FakeRedis:
    def __init__(self) -> None:
        self.lists: dict[str, deque[str]] = {}
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}

    def ping(self) -> bool:
        return True

    def rpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, deque()).append(value)
        return len(self.lists[key])

    def brpop(self, key: str, timeout: float = 0.0):
        queue = self.lists.get(key)
        if not queue:
            return None
        return key, queue.popleft()

    def xread(self, streams: dict[str, str], count: int = 1, block: int = 1):
        for stream, _cursor in streams.items():
            entries = self.streams.get(stream, [])
            if entries:
                msg_id, fields = entries[0]
                return [(stream, [(msg_id, fields)])]
        return []

    def xdel(self, stream: str, msg_id: str) -> None:
        entries = self.streams.get(stream, [])
        self.streams[stream] = [item for item in entries if item[0] != msg_id]


@pytest.mark.unit
def test_redis_list_enqueue_dequeue_two_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr("redis.Redis.from_url", lambda *_args, **_kwargs: fake)
    queue = RedisJobQueue(redis_url="redis://localhost:6379/0")
    first = {"job_id": "j1", "persona": "consultant"}
    second = {"job_id": "j2", "persona": "consultant"}
    queue.enqueue(first)
    queue.enqueue(second)
    assert queue.dequeue(0.1) == first
    assert queue.dequeue(0.1) == second
    assert queue.dequeue(0.0) is None


@pytest.mark.unit
def test_redis_brpop_safe_for_multiple_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr("redis.Redis.from_url", lambda *_args, **_kwargs: fake)
    queue_a = RedisJobQueue(redis_url="redis://localhost:6379/0")
    queue_b = RedisJobQueue(redis_url="redis://localhost:6379/0")
    payload = {"job_id": "j-only", "persona": "consultant"}
    queue_a.enqueue(payload)
    assert queue_a.dequeue(0.1) == payload
    assert queue_b.dequeue(0.0) is None


@pytest.mark.unit
def test_redis_drains_legacy_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    fake.streams[RedisJobQueue.STREAM_KEY] = [
        ("1-0", {"payload": json.dumps({"job_id": "legacy-1", "persona": "consultant"})})
    ]
    monkeypatch.setattr("redis.Redis.from_url", lambda *_args, **_kwargs: fake)
    queue = RedisJobQueue(redis_url="redis://localhost:6379/0")
    job = queue.dequeue(0.1)
    assert job is not None
    assert job["job_id"] == "legacy-1"
