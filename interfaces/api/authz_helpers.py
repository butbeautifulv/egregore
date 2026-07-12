"""Shared FGA helpers for HTTP handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bootstrap.container import get_container
from cys_core.application.authz.service import AuthzDenied
from cys_core.application.ports.job_store import JobRecord
from interfaces.api.authz_deps import _authz_user_from_bearer
from interfaces.api.errors import authz_denied_http

if TYPE_CHECKING:
    from cys_core.domain.security.auth_models import AuthClaims


def visible_engagement_ids(auth: AuthClaims | None) -> set[str] | None:
    """Engagement ids visible via FGA; None when filtering disabled."""
    authz = get_container().get_authz_service()
    if authz.mode == "off" or auth is None:
        return None
    user = f"user:{auth.sub}"
    return set(authz.list_objects(user=user, relation="can_view", object_type="engagement"))


def visible_workspace_ids(auth: AuthClaims | None) -> set[str] | None:
    """Workspace ids the user may view; None when FGA filtering is disabled."""
    authz = get_container().get_authz_service()
    if authz.mode == "off" or auth is None:
        return None
    user = f"user:{auth.sub}"
    ids = authz.list_objects(user=user, relation="can_view", object_type="workspace")
    return set(ids)


def filter_by_visible_workspaces(items, visible: set[str] | None):
    if visible is None:
        return items
    return [
        item
        for item in items
        if not (getattr(item, "workspace_id", "") or "") or item.workspace_id in visible
    ]


def require_workspace_relation(
    auth: AuthClaims | None,
    authorization: str | None,
    workspace_id: str,
    relation: str,
) -> None:
    workspace_id = (workspace_id or "").strip()
    authz = get_container().get_authz_service()
    if not workspace_id:
        if authz.mode == "enforce":
            raise authz_denied_http()
        return
    if authz.mode == "off":
        return
    user = f"user:{auth.sub}" if auth and auth.sub else _authz_user_from_bearer(authorization)
    try:
        authz.check(user, relation, f"workspace:{workspace_id}")
    except AuthzDenied as exc:
        raise authz_denied_http() from exc


def engagement_workspace_id(tenant_id: str, engagement_id: str) -> str:
    engagement = get_container().get_engagement_state_store().get(tenant_id, engagement_id)
    if engagement is None:
        return ""
    return (getattr(engagement, "workspace_id", "") or "").strip()


def workspace_id_for_job(tenant_id: str, record: JobRecord) -> str:
    investigation_id = (record.correlation_id or record.session_id or "").strip()
    if not investigation_id:
        return ""
    return engagement_workspace_id(tenant_id, investigation_id)


def count_active_jobs_for_workspace(organization_id: str, workspace_id: str) -> int:
    eng_store = get_container().get_engagement_state_store()
    job_store = get_container().get_job_store()
    total = 0
    for engagement in eng_store.list_recent(organization_id, limit=10_000):
        if (getattr(engagement, "workspace_id", "") or "") != workspace_id:
            continue
        total += job_store.count_active_bus_jobs(organization_id, engagement.id)
    return total


def require_engagement_relation(
    *,
    auth: AuthClaims | None,
    authorization: str | None = None,
    tenant_id: str,
    engagement_id: str,
    relation: str,
) -> None:
    workspace_id = engagement_workspace_id(tenant_id, engagement_id)
    require_workspace_relation(auth, authorization, workspace_id, relation)
