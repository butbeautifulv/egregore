from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from bootstrap.settings import get_settings
from cys_core.domain.security.auth_models import AuthClaims, AuthError
from cys_core.infrastructure.auth.factory import get_token_verifier


def require_role_setting(*setting_fields: str):
    """FastAPI dependency factory: verify JWT and optional RBAC roles from settings."""

    async def _dependency(
        authorization: Annotated[str | None, Header()] = None,
    ) -> AuthClaims | None:
        settings = get_settings()
        if not settings.auth_enabled:
            return None
        verifier = get_token_verifier()
        try:
            claims = verifier.verify_bearer(authorization)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if settings.rbac_enabled and setting_fields:
            required_roles = tuple(getattr(settings, field) for field in setting_fields)
            if not claims.has_any_role(*required_roles):
                raise HTTPException(status_code=403, detail="Forbidden")
        return claims

    return _dependency


require_ingress_role = require_role_setting("rbac_role_ingress")
require_reader_role = require_role_setting("rbac_role_reader")
require_operator_role = require_role_setting("rbac_role_operator")
