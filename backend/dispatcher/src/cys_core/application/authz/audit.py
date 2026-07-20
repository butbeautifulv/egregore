"""Structured authz audit events (ADR-005)."""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def log_authz_deny(
    *,
    user: str,
    relation: str,
    object: str,
    organization_id: str = "",
    workspace_id: str = "",
) -> None:
    logger.info(
        "authz_deny",
        user=user,
        relation=relation,
        object=object,
        organization_id=organization_id,
        workspace_id=workspace_id,
    )


def log_grant_change(
    *,
    action: str,
    workspace_id: str,
    actor: str,
    relation: str,
    target: str = "",
    organization_id: str = "",
) -> None:
    logger.info(
        "authz_grant_change",
        action=action,
        workspace_id=workspace_id,
        actor=actor,
        relation=relation,
        target=target,
        organization_id=organization_id,
    )
