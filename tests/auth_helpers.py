from __future__ import annotations

import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _StaticJWKClient:
    def __init__(self, private_key: rsa.RSAPrivateKey) -> None:
        self._public_key = private_key.public_key()

    def get_signing_key_from_jwt(self, token: str) -> Any:
        return type("SigningKey", (), {"key": self._public_key})()


def sign_access_token(
    private_key: rsa.RSAPrivateKey,
    *,
    issuer: str,
    audience: str = "egregore-api",
    sub: str = "test-user",
    roles: list[str] | None = None,
    ttl_seconds: int = 3600,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "exp": now + ttl_seconds,
        "iat": now,
    }
    if roles:
        claims["realm_access"] = {"roles": roles}
        claims["resource_access"] = {"egregore-api": {"roles": roles}}
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-kid"})
