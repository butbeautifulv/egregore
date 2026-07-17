from __future__ import annotations

from bootstrap.container import get_container
from cys_core.domain.security.auth_models import AuthClaims, AuthError

# Self-contained rather than importing interfaces.api.auth.require_role_setting
# (interfaces/api/ is api-only per the split — see plan §0.1/§1 — this Tool
# Gateway is worker's own separate HTTP service and must not depend on it).
# Same logic as interfaces/api/auth.py's require_role_setting; kept small
# enough that duplicating it here is simpler than a shared abstraction over
# a get_container() that api and worker will eventually implement differently.


class GatewayAuthError(Exception):
    """Transport-agnostic auth failure — server.py maps this to an HTTP status."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def get_token_verifier():
    return get_container().get_token_verifier()


async def require_gateway_role(authorization: str | None) -> AuthClaims | None:
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
        raise GatewayAuthError(401, str(exc)) from exc
    if settings.rbac_enabled:
        if not claims.has_any_role(settings.rbac_role_gateway):
            raise GatewayAuthError(403, "Forbidden")
    return claims


__all__ = ["GatewayAuthError", "require_gateway_role"]
