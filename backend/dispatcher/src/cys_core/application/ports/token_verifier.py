from __future__ import annotations

from typing import Protocol

from cys_core.domain.security.auth_models import AuthClaims


class TokenVerifier(Protocol):
    """Port for validating Bearer JWT access tokens."""

    def verify_bearer(self, authorization_header: str | None) -> AuthClaims: ...
