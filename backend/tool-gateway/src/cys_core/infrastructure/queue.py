from __future__ import annotations

import json
from collections import deque
from typing import Any

import structlog

from bootstrap.settings import Settings
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.redis_client import ResilientRedisClient
from cys_core.observability.metrics import metrics

logger = structlog.get_logger(__name__)


class InMemoryJobQueue:
    """Fallback job queue when Redis is unavailable."""

    name = "memory"

    def __init__(self) -> None:
        self._queue: deque[WorkerJob] = deque()

    def enqueue(self, job: WorkerJob) -> str:
        self._queue.append(job)
        return job.job_id

    def enqueue_front(self, job: WorkerJob) -> str:
        self._queue.appendleft(job)
        return job.job_id

    def dequeue(self, timeout: float = 0.0) -> WorkerJob | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    async def aenqueue(self, job: WorkerJob) -> str:
        return self.enqueue(job)

    async def aenqueue_front(self, job: WorkerJob) -> str:
        return self.enqueue_front(job)

    async def adequeue(self, timeout: float = 0.0) -> WorkerJob | None:
        return self.dequeue(timeout)

    async def aclose(self) -> None:
        return None

    def queue_depth(self) -> int:
        return len(self._queue)

    def purge_engagement_jobs(self, engagement_id: str) -> int:
        if not engagement_id:
            return 0
        kept: deque[WorkerJob] = deque()
        removed = 0
        while self._queue:
            job = self._queue.popleft()
            if engagement_id in (job.correlation_id or ""):
                removed += 1
            else:
                kept.append(job)
        self._queue = kept
        return removed


class RedisJobQueue:
    """Redis LIST-backed worker job queue (BRPOP — safe for multiple workers)."""

    name = "redis"
    STREAM_KEY = "cys:worker:jobs"
    LIST_KEY = "cys:worker:jobs:queue"

    def __init__(self, *, settings: Settings) -> None:
        self._fallback = InMemoryJobQueue()
        self._logged_backend = False
        self._redis_url = settings.redis_url
        self._strict_redis = settings.strict_redis_queue
        self._redis_client = ResilientRedisClient(
            self._redis_url,
            strict=self._strict_redis,
            unavailable_error="redis_queue_unavailable",
        )

    @property
    def _redis(self) -> Any:
        if self._redis_client.ensure_connected():
            return self._redis_client.client
        return None

    @_redis.setter
    def _redis(self, value: Any) -> None:
        if value is None:
            self._redis_client.invalidate()

    def _connect_redis(self) -> Any:
        return self._redis_client.client

    def _ensure_redis(self) -> bool:
        return self._redis_client.ensure_connected()

    @property
    def active_backend(self) -> str:
        return "redis" if self._redis is not None else "memory"

    def _log_backend_once(self) -> None:
        if self._logged_backend:
            return
        self._logged_backend = True
        logger.info("job_queue_backend", queue_backend=self.active_backend, redis_url=self._redis_url)

    def _strict_redis_required(self) -> bool:
        return self._strict_redis

    def _reject_memory_fallback(self, *, reason: str) -> None:
        if self._strict_redis_required():
            raise RuntimeError(f"redis_queue_unavailable:{reason}")

    def _use_memory_fallback(self, *, reason: str) -> InMemoryJobQueue:
        self._reject_memory_fallback(reason=reason)
        metrics.record_infrastructure_fallback("redis_queue", reason=reason)
        self._log_backend_once()
        logger.warning("queue_memory_fallback", reason=reason, queue_backend="memory")
        return self._fallback

    def enqueue(self, job: WorkerJob) -> str:
        if not self._ensure_redis():
            return self._use_memory_fallback(reason="enqueue").enqueue(job)
        self._log_backend_once()
        try:
            payload = json.dumps(job.model_dump(mode="json"), ensure_ascii=False)
            self._redis.rpush(self.LIST_KEY, payload)
            return job.job_id
        except Exception:
            self._redis = None
            return self._use_memory_fallback(reason="enqueue_error").enqueue(job)

    def enqueue_front(self, job: WorkerJob) -> str:
        if not self._ensure_redis():
            return self._use_memory_fallback(reason="enqueue_front").enqueue_front(job)
        self._log_backend_once()
        try:
            payload = json.dumps(job.model_dump(mode="json"), ensure_ascii=False)
            self._redis.lpush(self.LIST_KEY, payload)
            return job.job_id
        except Exception:
            self._redis = None
            return self._use_memory_fallback(reason="enqueue_front_error").enqueue_front(job)

    def _dequeue_list(self, timeout: float) -> WorkerJob | None:
        block = max(1, int(timeout * 1000)) if timeout > 0 else 1
        result = self._redis.brpop(self.LIST_KEY, timeout=block / 1000.0)
        if not result:
            return None
        _, payload = result
        return WorkerJob.model_validate(json.loads(payload))

    def _drain_legacy_stream(self) -> WorkerJob | None:
        """One-time drain of pre-migration stream entries."""
        entries = self._redis.xread({self.STREAM_KEY: "0"}, count=1, block=1)
        if not entries:
            return None
        _stream, messages = entries[0]
        msg_id, fields = messages[0]
        self._redis.xdel(self.STREAM_KEY, msg_id)
        return WorkerJob.model_validate(json.loads(fields["payload"]))

    def dequeue(self, timeout: float = 0.0) -> WorkerJob | None:
        if not self._ensure_redis():
            return self._use_memory_fallback(reason="dequeue").dequeue(timeout)
        self._log_backend_once()
        try:
            job = self._dequeue_list(timeout)
            if job is not None:
                return job
            return self._drain_legacy_stream()
        except Exception:
            self._redis = None
            return self._use_memory_fallback(reason="dequeue_error").dequeue(timeout)

    async def aenqueue(self, job: WorkerJob) -> str:
        import asyncio

        return await asyncio.to_thread(self.enqueue, job)

    async def aenqueue_front(self, job: WorkerJob) -> str:
        import asyncio

        return await asyncio.to_thread(self.enqueue_front, job)

    async def adequeue(self, timeout: float = 0.0) -> WorkerJob | None:
        import asyncio

        # dequeue() already calls _ensure_redis() internally and falls back to the in-memory
        # queue on failure — no need for a separate pre-check here, just offload the whole call
        # (previously there was a redundant, *unwrapped* _ensure_redis() check before this: with
        # ensure_connected() now retrying with backoff (docs/MICROSERVICES_SPLIT_PLAN.md §33), that
        # would have blocked the event loop for the whole retry duration whenever Redis is down).
        return await asyncio.to_thread(self.dequeue, timeout)

    async def aclose(self) -> None:
        return None

    def queue_depth(self) -> int | None:
        if not self._ensure_redis():
            return self._fallback.queue_depth()
        try:
            return int(self._redis.llen(self.LIST_KEY))
        except Exception:
            self._redis = None
            return self._fallback.queue_depth()

    def purge_engagement_jobs(self, engagement_id: str) -> int:
        if not engagement_id:
            return 0
        if not self._ensure_redis():
            return self._fallback.purge_engagement_jobs(engagement_id)
        try:
            raw_jobs = self._redis.lrange(self.LIST_KEY, 0, -1)
            if not raw_jobs:
                return 0
            kept: list[str] = []
            removed = 0
            for payload in raw_jobs:
                job = WorkerJob.model_validate(json.loads(payload))
                if engagement_id in (job.correlation_id or ""):
                    removed += 1
                else:
                    kept.append(payload)
            pipe = self._redis.pipeline()
            pipe.delete(self.LIST_KEY)
            if kept:
                pipe.rpush(self.LIST_KEY, *kept)
            pipe.execute()
            return removed
        except Exception:
            self._redis = None
            return self._fallback.purge_engagement_jobs(engagement_id)


_queues: dict[str | None, JobQueueConnector] = {}


def get_job_queue(
    persona: str | None = None,
    *,
    settings: Settings,
) -> JobQueueConnector:
    """Return job queue connector; Kafka when USE_KAFKA=true."""
    if persona in _queues:
        return _queues[persona]
    if settings.use_kafka:
        from cys_core.infrastructure.kafka_queue import KafkaJobQueue

        queue: JobQueueConnector = KafkaJobQueue(persona=persona, settings=settings)
    else:
        queue = RedisJobQueue(settings=settings)
    _queues[persona] = queue
    return queue


def reset_job_queue_cache() -> None:
    """Clear cached queue instances (tests)."""
    _queues.clear()
