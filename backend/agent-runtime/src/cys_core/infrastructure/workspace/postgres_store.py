from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, cast

from psycopg.rows import dict_row

from cys_core.domain.workspace.models import Workspace, WorkspaceAgent
from cys_core.infrastructure.postgres_retry import connect_with_retry

WORKSPACE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    soft_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS workspaces_org_idx ON workspaces (organization_id) WHERE NOT soft_deleted;

CREATE TABLE IF NOT EXISTS workspace_agents (
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, name)
);
"""


class PostgresWorkspaceStore:
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url
        self._ensure_schema()

    def _connect(self):
        return connect_with_retry(self._postgres_url, row_factory=cast(Any, dict_row))

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(WORKSPACE_SCHEMA_SQL)
            conn.commit()

    def create(self, workspace: Workspace) -> Workspace:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO workspaces (id, organization_id, payload, soft_deleted, updated_at)
                VALUES (%s, %s, %s::jsonb, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    organization_id = EXCLUDED.organization_id,
                    soft_deleted = EXCLUDED.soft_deleted,
                    updated_at = NOW()
                """,
                (
                    workspace.id,
                    workspace.organization_id,
                    json.dumps(workspace.model_dump(mode="json")),
                    workspace.soft_deleted,
                ),
            )
            conn.commit()
        return workspace

    def get(self, workspace_id: str) -> Workspace | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload, soft_deleted FROM workspaces WHERE id = %s",
                (workspace_id,),
            ).fetchone()
        if row is None or row["soft_deleted"]:
            return None
        return Workspace.model_validate(row["payload"])

    def list_by_organization(self, organization_id: str) -> list[Workspace]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload FROM workspaces
                WHERE organization_id = %s AND NOT soft_deleted
                ORDER BY payload->>'name'
                """,
                (organization_id,),
            ).fetchall()
        return [Workspace.model_validate(r["payload"]) for r in rows]

    def update(self, workspace: Workspace) -> Workspace:
        workspace.updated_at = datetime.now(timezone.utc)
        return self.create(workspace)

    def soft_delete(self, workspace_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE workspaces SET soft_deleted = TRUE, updated_at = NOW()
                WHERE id = %s AND NOT soft_deleted
                """,
                (workspace_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def upsert_agent(self, agent: WorkspaceAgent) -> WorkspaceAgent:
        agent.updated_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO workspace_agents (workspace_id, name, payload, updated_at)
                VALUES (%s, %s, %s::jsonb, NOW())
                ON CONFLICT (workspace_id, name) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    updated_at = NOW()
                """,
                (agent.workspace_id, agent.name, json.dumps(agent.model_dump(mode="json"))),
            )
            conn.commit()
        return agent

    def get_agent(self, workspace_id: str, name: str) -> WorkspaceAgent | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM workspace_agents WHERE workspace_id = %s AND name = %s",
                (workspace_id, name),
            ).fetchone()
        if row is None:
            return None
        return WorkspaceAgent.model_validate(row["payload"])

    def list_agents(self, workspace_id: str) -> list[WorkspaceAgent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM workspace_agents WHERE workspace_id = %s ORDER BY name",
                (workspace_id,),
            ).fetchall()
        return [WorkspaceAgent.model_validate(r["payload"]) for r in rows]

    def delete_agent(self, workspace_id: str, name: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM workspace_agents WHERE workspace_id = %s AND name = %s",
                (workspace_id, name),
            )
            conn.commit()
            return cur.rowcount > 0
