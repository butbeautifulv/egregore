from __future__ import annotations

from typing import Any, Protocol


class RunRuntime(Protocol):
    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        tenant_id: str = "default",
        investigation_id: str = "",
        profile_id: str = "cybersec-soc",
    ) -> dict[str, Any]: ...
