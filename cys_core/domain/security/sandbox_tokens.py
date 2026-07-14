from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxTokenClaims:
    run_id: str
    persona: str
    tenant_id: str
    job_id: str
    exp: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.exp


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def mint_sandbox_token(
    *,
    run_id: str,
    persona: str,
    tenant_id: str,
    job_id: str,
    ttl_s: float,
    secret: bytes,
) -> str:
    """Short-lived, signed token binding a sandbox run to one job/persona/tenant.

    Not a capability token by itself — it identifies and time-bounds a sandbox
    run for audit/tracing today. Verifying it at the MCP Tool Gateway (reject
    tool calls from an expired or mismatched run_id) is the next hardening step,
    not yet wired.
    """
    payload = {
        "run_id": run_id,
        "persona": persona,
        "tenant_id": tenant_id,
        "job_id": job_id,
        "exp": time.time() + ttl_s,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64url(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_sandbox_token(token: str, *, secret: bytes) -> SandboxTokenClaims | None:
    """Return claims if the token is well-formed, correctly signed, and unexpired; else None."""
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        return None
    expected = _b64url(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_b64url_decode(body))
        claims = SandboxTokenClaims(
            run_id=str(payload["run_id"]),
            persona=str(payload["persona"]),
            tenant_id=str(payload["tenant_id"]),
            job_id=str(payload["job_id"]),
            exp=float(payload["exp"]),
        )
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if claims.expired:
        return None
    return claims
