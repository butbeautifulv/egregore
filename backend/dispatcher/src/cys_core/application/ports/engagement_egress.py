from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class EngagementEgressPort(Protocol):
    """Outbound engagement events for UI, webhooks, and SSE."""

    def publish_status(self, engagement_id: str, phase: str, payload: dict[str, Any]) -> None: ...

    def publish_event(self, engagement_id: str, event_type: str, payload: dict[str, Any]) -> None: ...

    def subscribe(self, engagement_id: str, *, tenant_id: str = "default") -> AsyncIterator[dict[str, Any]]: ...
