from __future__ import annotations

import json
from collections import deque
from functools import lru_cache
from typing import Any

from config import settings


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
    """Redis Streams-backed worker job queue."""

    name = "redis"
    STREAM_KEY = "cys:worker:jobs"

    def __init__(self, redis_url: str | None = None) -> None:
        self._fallback = InMemoryJobQueue()
        self._redis = None
        self._async_redis = None
        self._redis_url = redis_url or settings.redis_url
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
        self._redis.xadd(self.STREAM_KEY, {"payload": json.dumps(job, ensure_ascii=False)})
        return job_id

    def dequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        if self._redis is None:
            return self._fallback.dequeue(timeout)
        block = int(timeout * 1000) if timeout > 0 else 1
        entries = self._redis.xread({self.STREAM_KEY: "0"}, count=1, block=block)
        if not entries:
            return None
        _stream, messages = entries[0]
        msg_id, fields = messages[0]
        self._redis.xdel(self.STREAM_KEY, msg_id)
        return json.loads(fields["payload"])

    async def aenqueue(self, job: dict[str, Any]) -> str:
        return self.enqueue(job)

    async def adequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        return self.dequeue(timeout)


@lru_cache
def get_job_queue() -> RedisJobQueue:
    if settings.use_kafka:
        from cys_core.infrastructure.kafka_queue import KafkaJobQueue
        return KafkaJobQueue()  # type: ignore[return-value]
    return RedisJobQueue()
