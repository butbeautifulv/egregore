from __future__ import annotations

from typing import Any, Protocol

from cys_core.application.ports.stream_context import StreamContext


class AgentRunner(Protocol):
    """Port for running agent personas inside worker jobs."""

    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        sandbox_tools: list[Any] | None = None,
        job_id: str | None = None,
        event_id: str | None = None,
        correlation_id: str | None = None,
        tenant_id: str | None = None,
        investigation_id: str | None = None,
        sandbox_id: str | None = None,
        stream_context: StreamContext | None = None,
    ) -> dict[str, Any]: ...

    async def aresume(self, name: str, session_id: str, resume: dict[str, Any]) -> dict[str, Any]: ...
