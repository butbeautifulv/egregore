from __future__ import annotations

from typing import Any

from cys_core.application.ports.catalog_audit import CatalogAuditPort
from cys_core.infrastructure.catalog.audit import list_catalog_audit, record_catalog_change


class InMemoryCatalogAudit(CatalogAuditPort):
    def record_change(
        self,
        action: str,
        *,
        agent: str,
        actor: str = "api",
        details: dict[str, Any] | None = None,
        resource_type: str = "agent",
        resource_id: str | None = None,
    ) -> None:
        record_catalog_change(
            action,
            agent=agent,
            actor=actor,
            details=details,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    def list_entries(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return list_catalog_audit(limit=limit)
