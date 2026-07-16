"""Stable API error codes for AuthN/AuthZ (ADR-005)."""

from __future__ import annotations

from fastapi import HTTPException


def authz_denied_http(*, message: str = "Authorization denied") -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={"code": "AUTHZ_DENIED", "message": message},
    )


def tenant_mismatch_http(message: str) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={"code": "TENANT_MISMATCH", "message": message},
    )


def missing_organization_claim_http(message: str) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={"code": "MISSING_ORGANIZATION_CLAIM", "message": message},
    )


def workspace_active_jobs_http(*, count: int) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "WORKSPACE_HAS_ACTIVE_JOBS",
            "message": f"Workspace has {count} active job(s); wait for completion before delete",
            "active_jobs": count,
        },
    )


def control_agent_immutable_http() -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "code": "CONTROL_AGENT_IMMUTABLE",
            "message": "Control personas are immutable platform agents",
        },
    )
