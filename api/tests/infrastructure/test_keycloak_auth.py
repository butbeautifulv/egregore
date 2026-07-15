from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from cys_core.domain.security.auth_models import (
    ROLE_GATEWAY,
    ROLE_INGRESS,
    ROLE_OPERATOR,
    ROLE_READER,
    AuthClaims,
    AuthError,
    claims_from_payload,
    extract_roles,
)
from cys_core.infrastructure.auth.keycloak import KeycloakJwtVerifier


def _generate_rsa_keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _sign_token(
    private_key: rsa.RSAPrivateKey,
    *,
    kid: str,
    issuer: str,
    audience: str,
    sub: str,
    azp: str = "",
    ttl_seconds: int = 3600,
    roles: list[str] | None = None,
    client_id: str = "egregore-api",
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "iss": issuer,
        "exp": now + ttl_seconds,
        "iat": now,
    }
    if audience:
        claims["aud"] = audience
    if azp:
        claims["azp"] = azp
    if roles:
        claims["realm_access"] = {"roles": roles}
        claims["resource_access"] = {client_id: {"roles": roles}}
    token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})
    return token


class _StaticJWKClient:
    def __init__(self, private_key: rsa.RSAPrivateKey) -> None:
        self._public_key = private_key.public_key()

    def get_signing_key_from_jwt(self, token: str) -> Any:
        return type("SigningKey", (), {"key": self._public_key})()


@pytest.mark.unit
def test_extract_roles_merges_realm_and_client_roles():
    claims = {
        "realm_access": {"roles": ["egregore-reader"]},
        "resource_access": {"egregore-api": {"roles": ["egregore-ingress"]}},
    }
    roles = extract_roles(claims, "egregore-api")
    assert "egregore-reader" in roles
    assert "egregore-ingress" in roles


@pytest.mark.unit
def test_claims_from_payload_requires_subject():
    with pytest.raises(AuthError, match="missing subject"):
        claims_from_payload({}, client_id="egregore-api")


@pytest.mark.unit
def test_keycloak_verifier_valid_token():
    private_key = _generate_rsa_keypair()
    issuer = "https://keycloak.example/realms/cxado"
    verifier = KeycloakJwtVerifier(
        issuer=issuer,
        audience="egregore-api",
        client_id="egregore-api",
        jwks_client=_StaticJWKClient(private_key),
    )
    token = _sign_token(
        private_key,
        kid="test-kid",
        issuer=issuer,
        audience="egregore-api",
        sub="user-1",
        roles=[ROLE_INGRESS],
    )
    claims = verifier.verify_bearer(f"Bearer {token}")
    assert claims.sub == "user-1"
    assert claims.has_any_role(ROLE_INGRESS)


@pytest.mark.unit
def test_keycloak_verifier_rejects_missing_bearer():
    private_key = _generate_rsa_keypair()
    verifier = KeycloakJwtVerifier(
        issuer="https://keycloak.example/realms/cxado",
        audience="egregore-api",
        client_id="egregore-api",
        jwks_client=_StaticJWKClient(private_key),
    )
    with pytest.raises(AuthError, match="missing bearer token"):
        verifier.verify_bearer(None)


@pytest.mark.unit
def test_keycloak_verifier_rejects_expired_token():
    private_key = _generate_rsa_keypair()
    issuer = "https://keycloak.example/realms/cxado"
    verifier = KeycloakJwtVerifier(
        issuer=issuer,
        audience="egregore-api",
        client_id="egregore-api",
        jwks_client=_StaticJWKClient(private_key),
    )
    token = _sign_token(
        private_key,
        kid="test-kid",
        issuer=issuer,
        audience="egregore-api",
        sub="user-1",
        ttl_seconds=-10,
    )
    with pytest.raises(AuthError, match="invalid token"):
        verifier.verify_bearer(f"Bearer {token}")


@pytest.mark.unit
def test_keycloak_verifier_rejects_wrong_audience_without_azp():
    private_key = _generate_rsa_keypair()
    issuer = "https://keycloak.example/realms/cxado"
    verifier = KeycloakJwtVerifier(
        issuer=issuer,
        audience="egregore-api",
        client_id="egregore-api",
        jwks_client=_StaticJWKClient(private_key),
    )
    token = _sign_token(
        private_key,
        kid="test-kid",
        issuer=issuer,
        audience="other-client",
        sub="user-1",
    )
    with pytest.raises(AuthError, match="invalid audience"):
        verifier.verify_bearer(f"Bearer {token}")


@pytest.mark.unit
def test_keycloak_verifier_accepts_azp_fallback():
    private_key = _generate_rsa_keypair()
    issuer = "https://keycloak.example/realms/cxado"
    verifier = KeycloakJwtVerifier(
        issuer=issuer,
        audience="egregore-api",
        client_id="egregore-api",
        jwks_client=_StaticJWKClient(private_key),
    )
    token = _sign_token(
        private_key,
        kid="test-kid",
        issuer=issuer,
        audience="",
        sub="user-1",
        azp="egregore-api",
        roles=[ROLE_GATEWAY],
    )
    claims = verifier.verify_bearer(f"Bearer {token}")
    assert claims.has_any_role(ROLE_GATEWAY)


@pytest.mark.unit
def test_auth_claims_has_any_role():
    claims = AuthClaims(sub="u1", roles=(ROLE_READER,))
    assert claims.has_any_role(ROLE_READER)
    assert not claims.has_any_role(ROLE_OPERATOR)
