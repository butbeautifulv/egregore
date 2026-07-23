from __future__ import annotations

from typing import Any, Protocol


class OrchestrationPort(Protocol):
    """Enqueue worker jobs from routing or bus messages."""

    async def enqueue_from_bus(self, envelope: dict[str, Any]) -> str: ...

    def enqueue_from_routing_sync(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
        profile_id: str | None = None,
        sequential: bool = False,
        pipeline_staged: bool = False,
    ) -> list[str]: ...

    async def enqueue_from_routing(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
        profile_id: str | None = None,
        sequential: bool = False,
        pipeline_staged: bool = False,
    ) -> list[str]: ...
