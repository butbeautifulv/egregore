from __future__ import annotations

import json
from collections import deque
from typing import Any

from bootstrap.settings import Settings, get_settings


class InMemoryJobQueue:
    """Fallback job queue when Redis is unavailable."""

    name = "memory"

    def __init__(self) -> None:
        self._queue: deque[dict[str, Any]] = deque()

    def enqueue(self, job: dict[str, Any]) -> str:
        job_id = job.get("job_id", "")
        self._queue.append(job)
        return job_id

    def dequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    async def aenqueue(self, job: dict[str, Any]) -> str:
        return self.enqueue(job)

    async def adequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        return self.dequeue(timeout)


class RedisJobQueue:
    """Redis LIST-backed worker job queue (BRPOP — safe for multiple workers)."""

    name = "redis"
    STREAM_KEY = "cys:worker:jobs"
    LIST_KEY = "cys:worker:jobs:queue"

    def __init__(self, redis_url: str | None = None, *, settings: Settings | None = None) -> None:
        self._fallback = InMemoryJobQueue()
        self._redis = None
        cfg = settings or get_settings()
        self._redis_url = redis_url or cfg.redis_url
        try:
            import redis

            self._redis = redis.Redis.from_url(self._redis_url, decode_responses=True)
            self._redis.ping()
        except Exception:
            self._redis = None

    def enqueue(self, job: dict[str, Any]) -> str:
        job_id = job.get("job_id", "")
        if self._redis is None:
            return self._fallback.enqueue(job)
        payload = json.dumps(job, ensure_ascii=False)
        self._redis.rpush(self.LIST_KEY, payload)
        return job_id

    def _dequeue_list(self, timeout: float) -> dict[str, Any] | None:
        block = max(1, int(timeout * 1000)) if timeout > 0 else 1
        result = self._redis.brpop(self.LIST_KEY, timeout=block / 1000.0)
        if not result:
            return None
        _, payload = result
        return json.loads(payload)

    def _drain_legacy_stream(self) -> dict[str, Any] | None:
        """One-time drain of pre-migration stream entries."""
        entries = self._redis.xread({self.STREAM_KEY: "0"}, count=1, block=1)
        if not entries:
            return None
        _stream, messages = entries[0]
        msg_id, fields = messages[0]
        self._redis.xdel(self.STREAM_KEY, msg_id)
        return json.loads(fields["payload"])

    def dequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        if self._redis is None:
            return self._fallback.dequeue(timeout)
        job = self._dequeue_list(timeout)
        if job is not None:
            return job
        return self._drain_legacy_stream()

    async def aenqueue(self, job: dict[str, Any]) -> str:
        return self.enqueue(job)

    async def adequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        import asyncio

        if self._redis is None:
            return self.dequeue(timeout)
        return await asyncio.to_thread(self.dequeue, timeout)


_queues: dict[str | None, RedisJobQueue | InMemoryJobQueue] = {}


def get_job_queue(
    persona: str | None = None,
    *,
    settings: Settings | None = None,
) -> RedisJobQueue | InMemoryJobQueue:
    """Return job queue connector; Kafka when USE_KAFKA=true."""
    cfg = settings or get_settings()
    if persona in _queues:
        return _queues[persona]
    if cfg.use_kafka:
        from cys_core.infrastructure.kafka_queue import KafkaJobQueue

        queue: RedisJobQueue | InMemoryJobQueue = KafkaJobQueue(persona=persona, settings=cfg)
    else:
        queue = RedisJobQueue(settings=cfg)
    _queues[persona] = queue
    return queue


def reset_job_queue_cache() -> None:
    """Clear cached queue instances (tests)."""
    _queues.clear()
