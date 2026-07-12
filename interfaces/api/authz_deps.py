from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from bootstrap.container import get_container
from cys_core.application.authz.service import AuthzDenied
from cys_core.domain.security.auth_models import AuthClaims, AuthError
from interfaces.api.auth import require_reader_role
from interfaces.api.errors import authz_denied_http


def _authz_user_from_bearer(authorization: str | None) -> str:
    settings = get_container().settings
    if not settings.auth_enabled:
        return "user:anonymous"
    verifier = get_container().get_token_verifier()
    try:
        claims = verifier.verify_bearer(authorization)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return f"user:{claims.sub}"


def require_relation(object_type: str, relation: str, object_id_param: str):
    """FastAPI dependency factory for OpenFGA object checks."""

    async def _dependency(
        request: Request,
        auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
        authorization: Annotated[str | None, Header()] = None,
    ) -> None:
        authz = get_container().get_authz_service()
        if authz.mode == "off":
            return
        object_id = str(request.path_params.get(object_id_param, "")).strip()
        if not object_id:
            raise HTTPException(status_code=400, detail={"code": "AUTHZ_OBJECT_ID_MISSING"})
        user = f"user:{auth.sub}" if auth and auth.sub else _authz_user_from_bearer(authorization)
        try:
            authz.check(user, relation, f"{object_type}:{object_id}")
        except AuthzDenied as exc:
            raise authz_denied_http() from exc

    return _dependency
