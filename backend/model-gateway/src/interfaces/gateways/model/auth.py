from __future__ import annotations

import hmac

from bootstrap.settings import get_settings


class GatewayAuthError(Exception):
    """Transport-agnostic auth failure — server.py maps this to an HTTP status."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def require_gateway_secret(authorization: str | None) -> None:
    settings = get_settings()
    if not settings.auth_enabled:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise GatewayAuthError(401, "missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, settings.shared_secret):
        raise GatewayAuthError(403, "Forbidden")


__all__ = ["GatewayAuthError", "require_gateway_secret"]
