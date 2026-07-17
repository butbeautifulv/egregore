from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from cys_core.application.ports.token_verifier import TokenVerifier
from cys_core.domain.security.auth_models import AuthClaims, AuthError
from cys_core.infrastructure.auth.keycloak import KeycloakJwtVerifier

if TYPE_CHECKING:
    from bootstrap.settings import Settings


class DisabledTokenVerifier:
    """No-op verifier used when AUTH_ENABLED=0."""

    def verify_bearer(self, authorization_header: str | None) -> AuthClaims:
        raise AuthError("auth disabled")


def build_token_verifier(settings: Settings) -> TokenVerifier:
    if not settings.auth_enabled:
        return DisabledTokenVerifier()
    return KeycloakJwtVerifier(
        issuer=settings.keycloak_issuer,
        audience=settings.keycloak_audience or settings.keycloak_client_id,
        client_id=settings.keycloak_client_id,
    )


@lru_cache
def get_token_verifier() -> TokenVerifier:
    from bootstrap.settings import get_settings

    return build_token_verifier(get_settings())
