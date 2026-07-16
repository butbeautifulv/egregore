from __future__ import annotations

import json
from typing import Any

import psycopg

from cys_core.application.ports.catalog_audit import CatalogAuditPort
from cys_core.infrastructure.catalog.audit import list_catalog_audit, record_catalog_change


class PostgresCatalogAudit(CatalogAuditPort):
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._postgres_url)

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
        resource_id = resource_id or agent
        record_catalog_change(
            action,
            agent=agent,
            actor=actor,
            details=details,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO catalog_audit (action, resource_type, resource_id, actor, details)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (action, resource_type, resource_id, actor, json.dumps(details or {})),
            )
            conn.commit()

    def list_entries(self, *, limit: int = 50) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT ts, action, resource_type, resource_id, actor, details
                    FROM catalog_audit ORDER BY ts DESC LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
            return [
                {
                    "ts": row[0].isoformat() if row[0] else "",
                    "action": row[1],
                    "resource_type": row[2],
                    "resource_id": row[3],
                    "actor": row[4],
                    "details": row[5] or {},
                }
                for row in rows
            ]
        except Exception:
            return list_catalog_audit(limit=limit)
