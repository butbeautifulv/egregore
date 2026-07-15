from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any


class NoopEngagementEgress:
    """Default egress when feature flags are off."""

    def publish_status(self, engagement_id: str, phase: str, payload: dict[str, Any]) -> None:
        return None

    def publish_event(self, engagement_id: str, event_type: str, payload: dict[str, Any]) -> None:
        return None

    async def subscribe(
        self, engagement_id: str, *, tenant_id: str = "default"
    ) -> AsyncIterator[dict[str, Any]]:
        if False:
            yield {}
        return
