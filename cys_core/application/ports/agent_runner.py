from __future__ import annotations

from typing import Any, Protocol


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
        sandbox_id: str | None = None,
    ) -> dict[str, Any]: ...

    async def aresume(self, name: str, session_id: str, resume: dict[str, Any]) -> dict[str, Any]: ...
