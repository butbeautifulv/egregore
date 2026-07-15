from __future__ import annotations

from typing import Any, Protocol


class CatalogAuditPort(Protocol):
    def record_change(
        self,
        action: str,
        *,
        agent: str,
        actor: str = "api",
        details: dict[str, Any] | None = None,
        resource_type: str = "agent",
        resource_id: str | None = None,
    ) -> None: ...

    def list_entries(self, *, limit: int = 50) -> list[dict[str, Any]]: ...
