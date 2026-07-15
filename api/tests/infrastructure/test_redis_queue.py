from __future__ import annotations

import json
from collections import deque

import pytest

from bootstrap.settings import Settings
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.queue import RedisJobQueue


def _redis_settings(redis_url: str = "redis://localhost:6379/0") -> Settings:
    return Settings(stage="test", redis_url=redis_url)


def _job(job_id: str, persona: str = "consultant") -> WorkerJob:
    return WorkerJob(job_id=job_id, event_id="evt-1", persona=persona)


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
    queue = RedisJobQueue(settings=_redis_settings())
    first = _job("j1")
    second = _job("j2")
    queue.enqueue(first)
    queue.enqueue(second)
    assert queue.dequeue(0.1) == first
    assert queue.dequeue(0.1) == second
    assert queue.dequeue(0.0) is None


@pytest.mark.unit
def test_redis_brpop_safe_for_multiple_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr("redis.Redis.from_url", lambda *_args, **_kwargs: fake)
    queue_a = RedisJobQueue(settings=_redis_settings())
    queue_b = RedisJobQueue(settings=_redis_settings())
    payload = _job("j-only")
    queue_a.enqueue(payload)
    assert queue_a.dequeue(0.1) == payload
    assert queue_b.dequeue(0.0) is None


@pytest.mark.unit
def test_redis_reconnects_after_init_ping_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    calls = {"n": 0}

    def _from_url(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("redis down at init")
        return fake

    monkeypatch.setattr("redis.Redis.from_url", _from_url)
    queue = RedisJobQueue(settings=_redis_settings())
    assert queue.active_backend == "memory"
    job = _job("reconnect-1")
    assert queue.enqueue(job) == job.job_id
    assert queue.active_backend == "redis"
    assert queue.dequeue(0.1) == job

    fake = _FakeRedis()
    fake.streams[RedisJobQueue.STREAM_KEY] = [
        ("1-0", {"payload": json.dumps({"job_id": "legacy-1", "event_id": "evt-legacy", "persona": "consultant"})})
    ]
    monkeypatch.setattr("redis.Redis.from_url", lambda *_args, **_kwargs: fake)
    queue = RedisJobQueue(settings=_redis_settings())
    job = queue.dequeue(0.1)
    assert job is not None
    assert job.job_id == "legacy-1"
