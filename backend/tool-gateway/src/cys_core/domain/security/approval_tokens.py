from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApprovalTokenClaims:
    tool_name: str
    args_hash: str
    exp: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.exp


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def args_hash(tool_args: dict[str, Any]) -> str:
    """Same shape as cys_core.domain.workers.hitl.params_hash (worker/api) — kept as an
    independent copy here since tool-gateway has no dependency on that module, not a
    re-implementation for its own sake."""
    payload = json.dumps(tool_args, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def mint_approval_token(*, tool_name: str, tool_args: dict[str, Any], ttl_s: float, secret: bytes) -> str:
    """Self-contained, signed capability token binding one refused tool call to its exact
    args — the retry-time counterpart of InvokeTool's HITL refusal (docs/MSP_BACKLOG.md §35/§58).

    Deliberately stateless (HMAC-signed, same shape as mint_sandbox_token/verify_sandbox_token
    in this same module's sibling) rather than a server-side pending-approval store: tool-gateway
    has no shared state with the runtime process that will present this token back on retry, and
    doesn't need any — the token itself carries everything needed to verify a retry is for the
    exact call that was actually refused, not a substituted, more dangerous one.
    """
    payload = {
        "tool_name": tool_name,
        "args_hash": args_hash(tool_args),
        "exp": time.time() + ttl_s,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64url(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_approval_token(token: str, *, secret: bytes) -> ApprovalTokenClaims | None:
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
        claims = ApprovalTokenClaims(
            tool_name=str(payload["tool_name"]),
            args_hash=str(payload["args_hash"]),
            exp=float(payload["exp"]),
        )
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if claims.expired:
        return None
    return claims
