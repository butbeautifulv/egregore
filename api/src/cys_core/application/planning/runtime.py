from __future__ import annotations

from typing import Any, Protocol

from cys_core.application.ports.stream_context import StreamContext


class PlannerRuntime(Protocol):
    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        tenant_id: str | None = None,
        investigation_id: str | None = None,
        profile_id: str | None = None,
        job_id: str | None = None,
        stream_context: StreamContext | None = None,
    ) -> dict[str, Any]: ...
