from __future__ import annotations

import jwt
from jwt import PyJWKClient

from cys_core.domain.security.auth_models import AuthClaims, AuthError, claims_from_payload


class KeycloakJwtVerifier:
    """Validate JWT access tokens against Keycloak JWKS (OIDC)."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        client_id: str,
        jwks_client: PyJWKClient | None = None,
    ) -> None:
        normalized_issuer = issuer.rstrip("/")
        if not normalized_issuer:
            raise ValueError("keycloak issuer is empty")
        self.issuer = normalized_issuer
        self.audience = audience.strip()
        self.client_id = client_id
        jwks_url = f"{self.issuer}/protocol/openid-connect/certs"
        self._jwks_client = jwks_client or PyJWKClient(jwks_url, cache_keys=True, lifespan=300)

    def verify_bearer(self, authorization_header: str | None) -> AuthClaims:
        token = _extract_bearer_token(authorization_header)
        if not token:
            raise AuthError("missing bearer token")
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            options: dict[str, bool] = {
                "require": ["exp", "sub", "iss"],
                "verify_aud": False,
            }
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                issuer=self.issuer,
                options=options,
            )
        except jwt.PyJWTError as exc:
            raise AuthError("invalid token") from exc

        if self.audience and not _audience_matches(payload, self.audience):
            raise AuthError("invalid audience")

        return claims_from_payload(payload, client_id=self.client_id)


def _extract_bearer_token(authorization_header: str | None) -> str:
    if not authorization_header:
        return ""
    parts = authorization_header.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return ""
    return parts[1].strip()


def _audience_matches(payload: dict[str, object], audience: str) -> bool:
    aud = payload.get("aud")
    if isinstance(aud, str) and aud == audience:
        return True
    if isinstance(aud, list) and audience in aud:
        return True
    azp = payload.get("azp")
    return isinstance(azp, str) and azp == audience
