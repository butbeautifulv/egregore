from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any


class MemoryEngagementEgress:
    """In-memory ring buffer per engagement for dev/test and SSE."""

    def __init__(self, *, max_events: int = 200) -> None:
        self._max_events = max_events
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._waiters: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)

    def _key(self, tenant_id: str, engagement_id: str) -> str:
        return f"{tenant_id}:{engagement_id}"

    def _append(self, key: str, event: dict[str, Any]) -> None:
        buf = self._events[key]
        buf.append(event)
        if len(buf) > self._max_events:
            del buf[: len(buf) - self._max_events]
        for queue in self._waiters.get(key, []):
            queue.put_nowait(event)

    def publish_status(self, engagement_id: str, phase: str, payload: dict[str, Any]) -> None:
        tenant_id = str(payload.get("tenant_id", "default"))
        self._append(
            self._key(tenant_id, engagement_id),
            {"type": "status", "phase": phase, "engagement_id": engagement_id, "payload": payload},
        )

    def publish_event(self, engagement_id: str, event_type: str, payload: dict[str, Any]) -> None:
        tenant_id = str(payload.get("tenant_id", "default"))
        self._append(
            self._key(tenant_id, engagement_id),
            {"type": event_type, "engagement_id": engagement_id, "payload": payload},
        )

    def snapshot(self, engagement_id: str, *, tenant_id: str = "default") -> list[dict[str, Any]]:
        return list(self._events.get(self._key(tenant_id, engagement_id), []))

    async def subscribe(self, engagement_id: str, *, tenant_id: str = "default") -> AsyncIterator[dict[str, Any]]:
        key = self._key(tenant_id, engagement_id)
        for existing in self._events.get(key, []):
            yield existing
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._waiters[key].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._waiters[key] = [q for q in self._waiters[key] if q is not queue]
