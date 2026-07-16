from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from bootstrap.container import get_container
from cys_core.domain.security.auth_models import AuthClaims, AuthError

# Self-contained rather than importing interfaces.api.auth.require_role_setting
# (interfaces/api/ is api-only per the split — see plan §0.1/§1 — this Tool
# Gateway is worker's own separate FastAPI app and must not depend on it).
# Same logic as interfaces/api/auth.py's require_role_setting; kept small
# enough that duplicating it here is simpler than a shared abstraction over
# a get_container() that api and worker will eventually implement differently.


def get_token_verifier():
    return get_container().get_token_verifier()


async def require_gateway_role(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthClaims | None:
    settings = get_container().settings
    if not settings.auth_enabled:
        return None
    # Calls the module-level get_token_verifier() above (not
    # get_container().get_token_verifier() inline) so tests can monkeypatch
    # interfaces.gateways.tool.auth.get_token_verifier the same way they
    # used to monkeypatch interfaces.api.auth.get_token_verifier.
    verifier = get_token_verifier()
    try:
        claims = verifier.verify_bearer(authorization)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if settings.rbac_enabled:
        if not claims.has_any_role(settings.rbac_role_gateway):
            raise HTTPException(status_code=403, detail="Forbidden")
    return claims


__all__ = ["require_gateway_role"]
