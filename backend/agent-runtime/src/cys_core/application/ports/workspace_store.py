from __future__ import annotations

from typing import Protocol

from cys_core.domain.workspace.models import Workspace, WorkspaceAgent


class WorkspaceStorePort(Protocol):
    def create(self, workspace: Workspace) -> Workspace:
        ...

    def get(self, workspace_id: str) -> Workspace | None:
        ...

    def list_by_organization(self, organization_id: str) -> list[Workspace]:
        ...

    def update(self, workspace: Workspace) -> Workspace:
        ...

    def soft_delete(self, workspace_id: str) -> bool:
        ...

    def upsert_agent(self, agent: WorkspaceAgent) -> WorkspaceAgent:
        ...

    def get_agent(self, workspace_id: str, name: str) -> WorkspaceAgent | None:
        ...

    def list_agents(self, workspace_id: str) -> list[WorkspaceAgent]:
        ...

    def delete_agent(self, workspace_id: str, name: str) -> bool:
        ...
