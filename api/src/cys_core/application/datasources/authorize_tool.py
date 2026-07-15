"""Unified tool authorization: profile allowlist + FGA can_query."""

from __future__ import annotations

from typing import Any

from cys_core.application.authz.service import AuthzDenied
from cys_core.application.datasources.exec_authz import authorize_tool_datasource
from cys_core.domain.datasources.authz import AuthorizationDecision
from cys_core.domain.tools.models import ToolInvokeCommand


def authorize_tool(
    command: ToolInvokeCommand,
    *,
    authz_service: Any | None = None,
    user_id: str = "",
) -> AuthorizationDecision | None:
    """
    Return datasource AuthorizationDecision when profile allowlist denies.
    Raises AuthzDenied when FGA rejects in enforce mode.
    Returns None when allowed.
    """
    decision = authorize_tool_datasource(
        command.tool_name,
        profile_id=command.profile_id,
        persona=command.persona,
    )
    if decision is not None and not decision.allowed:
        return decision
    if authz_service is None or authz_service.mode == "off":
        return None
    ws_id = (command.workspace_id or "").strip()
    if not ws_id:
        if authz_service.mode == "enforce":
            raise AuthzDenied(user=user_id or "user:anonymous", relation="can_query", object="datasource:*")
        return None
    subject = user_id or f"workspace:{ws_id}"
    try:
        binding_ds = command.tool_name
        authz_service.check(subject, "can_query", f"datasource:{binding_ds}")
    except AuthzDenied:
        if authz_service.mode == "shadow":
            return None
        raise
    return None
