from __future__ import annotations

import threading
from datetime import datetime, timezone

from cys_core.domain.workspace.models import Workspace, WorkspaceAgent


class InMemoryWorkspaceStore:
    def __init__(self) -> None:
        self._workspaces: dict[str, Workspace] = {}
        self._agents: dict[tuple[str, str], WorkspaceAgent] = {}
        self._lock = threading.Lock()

    def create(self, workspace: Workspace) -> Workspace:
        with self._lock:
            self._workspaces[workspace.id] = workspace
            return workspace

    def get(self, workspace_id: str) -> Workspace | None:
        with self._lock:
            ws = self._workspaces.get(workspace_id)
            if ws is None or ws.soft_deleted:
                return None
            return ws

    def list_by_organization(self, organization_id: str) -> list[Workspace]:
        with self._lock:
            return sorted(
                [
                    ws
                    for ws in self._workspaces.values()
                    if ws.organization_id == organization_id and not ws.soft_deleted
                ],
                key=lambda w: w.name,
            )

    def update(self, workspace: Workspace) -> Workspace:
        with self._lock:
            workspace.updated_at = datetime.now(timezone.utc)
            self._workspaces[workspace.id] = workspace
            return workspace

    def soft_delete(self, workspace_id: str) -> bool:
        with self._lock:
            ws = self._workspaces.get(workspace_id)
            if ws is None or ws.soft_deleted:
                return False
            ws.soft_deleted = True
            ws.updated_at = datetime.now(timezone.utc)
            return True

    def upsert_agent(self, agent: WorkspaceAgent) -> WorkspaceAgent:
        with self._lock:
            agent.updated_at = datetime.now(timezone.utc)
            self._agents[(agent.workspace_id, agent.name)] = agent
            return agent

    def get_agent(self, workspace_id: str, name: str) -> WorkspaceAgent | None:
        with self._lock:
            return self._agents.get((workspace_id, name))

    def list_agents(self, workspace_id: str) -> list[WorkspaceAgent]:
        with self._lock:
            return sorted(
                [a for (ws, _), a in self._agents.items() if ws == workspace_id],
                key=lambda a: a.name,
            )

    def delete_agent(self, workspace_id: str, name: str) -> bool:
        with self._lock:
            return self._agents.pop((workspace_id, name), None) is not None
