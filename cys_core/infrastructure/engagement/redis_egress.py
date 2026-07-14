from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import structlog

from cys_core.infrastructure.engagement.memory_egress import MemoryEngagementEgress
from cys_core.infrastructure.redis_client import ResilientRedisClient

logger = structlog.get_logger(__name__)


class RedisEngagementEgress:
    """Redis-backed engagement egress shared across API and worker processes."""

    def __init__(self, redis_url: str | None = None, *, settings) -> None:
        self._settings = settings
        self._fallback = MemoryEngagementEgress(max_events=settings.engagement_egress_max_events)
        self._logged_backend = False
        self._redis_url = redis_url or settings.redis_url
        self._redis_client = ResilientRedisClient(self._redis_url)

    @property
    def _redis(self) -> Any:
        if self._redis_client.ensure_connected():
            return self._redis_client.client
        return None

    @_redis.setter
    def _redis(self, value: Any) -> None:
        if value is None:
            self._redis_client.invalidate()

    def _ensure_redis(self) -> bool:
        return self._redis_client.ensure_connected()

    @property
    def active_backend(self) -> str:
        return "redis" if self._redis is not None else "memory"

    def _log_backend_once(self) -> None:
        if self._logged_backend:
            return
        self._logged_backend = True
        logger.info("engagement_egress_backend", egress_backend=self.active_backend, redis_url=self._redis_url)

    def _list_key(self, tenant_id: str, engagement_id: str) -> str:
        return f"cys:engagement:egress:{tenant_id}:{engagement_id}"

    def _notify_key(self, tenant_id: str, engagement_id: str) -> str:
        return f"{self._list_key(tenant_id, engagement_id)}:notify"

    def _append(self, tenant_id: str, engagement_id: str, event: dict[str, Any]) -> None:
        if not self._ensure_redis():
            self._log_backend_once()
            if event.get("type") == "status":
                self._fallback.publish_status(engagement_id, str(event.get("phase", "")), event.get("payload", {}))
            else:
                self._fallback.publish_event(engagement_id, str(event.get("type", "event")), event.get("payload", {}))
            return
        self._log_backend_once()
        try:
            key = self._list_key(tenant_id, engagement_id)
            max_events = self._settings.engagement_egress_max_events
            self._redis.rpush(key, json.dumps(event, ensure_ascii=False))
            self._redis.ltrim(key, -max_events, -1)
            self._redis.expire(key, self._settings.engagement_egress_ttl_s)
            self._redis.publish(self._notify_key(tenant_id, engagement_id), "1")
        except Exception as exc:
            logger.warning("engagement_egress_redis_publish_failed", error=str(exc))
            self._redis = None
            self._append(tenant_id, engagement_id, event)

    def publish_status(self, engagement_id: str, phase: str, payload: dict[str, Any]) -> None:
        tenant_id = str(payload.get("tenant_id", "default"))
        event = {"type": "status", "phase": phase, "engagement_id": engagement_id, "payload": payload}
        self._append(tenant_id, engagement_id, event)

    def publish_event(self, engagement_id: str, event_type: str, payload: dict[str, Any]) -> None:
        tenant_id = str(payload.get("tenant_id", "default"))
        event = {"type": event_type, "engagement_id": engagement_id, "payload": payload}
        self._append(tenant_id, engagement_id, event)

    def snapshot(self, engagement_id: str, *, tenant_id: str = "default") -> list[dict[str, Any]]:
        if not self._ensure_redis():
            return self._fallback.snapshot(engagement_id, tenant_id=tenant_id)
        try:
            raw_items = self._redis.lrange(self._list_key(tenant_id, engagement_id), 0, -1)
            return [json.loads(item) for item in raw_items]
        except Exception:
            self._redis = None
            return self._fallback.snapshot(engagement_id, tenant_id=tenant_id)

    async def subscribe(self, engagement_id: str, *, tenant_id: str = "default") -> AsyncIterator[dict[str, Any]]:
        if not self._ensure_redis():
            async for event in self._fallback.subscribe(engagement_id, tenant_id=tenant_id):
                yield event
            return

        seen = 0
        for event in self.snapshot(engagement_id, tenant_id=tenant_id):
            seen += 1
            yield event

        notify_key = self._notify_key(tenant_id, engagement_id)
        pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(notify_key)
        try:
            while True:
                message = await asyncio.to_thread(
                    pubsub.get_message,
                    timeout=self._settings.engagement_egress_pubsub_timeout_s,
                )
                if message is None:
                    await asyncio.sleep(self._settings.engagement_egress_pubsub_idle_sleep_s)
                    continue
                current = self.snapshot(engagement_id, tenant_id=tenant_id)
                while seen < len(current):
                    yield current[seen]
                    seen += 1
        finally:
            pubsub.unsubscribe(notify_key)
            pubsub.close()
