from __future__ import annotations

from collections.abc import Callable

from cys_core.application.ports.authz import AuthzTuple
from cys_core.application.ports.workspace_store import WorkspaceStorePort
from cys_core.domain.workspace.models import Workspace

WriteTuplesFn = Callable[[list[AuthzTuple]], None]


def workspace_authz_tuples(workspace: Workspace) -> list[AuthzTuple]:
    workspace_ref = f"workspace:{workspace.id}"
    tuples = [
        AuthzTuple(
            user=f"organization:{workspace.organization_id}",
            relation="organization",
            object=workspace_ref,
        ),
    ]
    created_by = (workspace.created_by or "").strip()
    if created_by and created_by != "system":
        tuples.append(
            AuthzTuple(
                user=f"user:{created_by}",
                relation="owner",
                object=workspace_ref,
            )
        )
    return tuples


def ensure_default_workspace(
    store: WorkspaceStorePort,
    org_id: str,
    *,
    write_tuples: WriteTuplesFn | None = None,
) -> Workspace:
    organization_id = (org_id or "default").strip() or "default"
    workspace_id = f"{organization_id}-default"
    existing = store.get(workspace_id)
    if existing is not None:
        return existing
    workspace = store.create(
        Workspace(
            id=workspace_id,
            organization_id=organization_id,
            name="Default",
            created_by="system",
        )
    )
    if write_tuples is not None:
        write_tuples(workspace_authz_tuples(workspace))
    return workspace
