from __future__ import annotations

from typing import Any, Protocol


class ToolExecutionGateway(Protocol):
    """Abstract execution boundary for tool calls (local vs gateway)."""

    def invoke(
        self,
        tool_name: str,
        args: dict[str, Any],
        *,
        persona: str,
        sandbox_id: str = "",
        job_id: str = "",
        correlation_id: str = "",
        profile_id: str = "",
    ) -> dict[str, Any]: ...

