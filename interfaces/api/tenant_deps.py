"""FastAPI tenant binding dependencies (ADR-005)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from cys_core.application.authz.tenant_bind import TenantMismatchError, require_tenant_match
from cys_core.domain.security.auth_models import AuthClaims
from interfaces.api.auth import require_reader_role
from interfaces.api.errors import tenant_mismatch_http


def require_tenant_match_http(
    auth: AuthClaims | None,
    tenant_id: str,
    *,
    enforce: bool = True,
) -> str:
    """FastAPI-friendly wrapper raising HTTP 403 with stable error code."""
    try:
        return require_tenant_match(auth, tenant_id, enforce=enforce)
    except TenantMismatchError as exc:
        raise tenant_mismatch_http(str(exc)) from exc


def TenantBound(param: str = "tenant_id"):
    """FastAPI dependency: bind query/body tenant_id to JWT organization."""

    async def _dependency(
        request: Request,
        auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
    ) -> str:
        raw = request.query_params.get(param)
        if raw is None and request.method in {"POST", "PUT", "PATCH"}:
            try:
                body = await request.json()
                if isinstance(body, dict):
                    raw = body.get(param)
            except Exception:
                raw = None
        return require_tenant_match_http(auth, raw or "default")

    return _dependency
