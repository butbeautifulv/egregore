"""Shared tenant / organization binding for AuthN (ADR-005)."""

from __future__ import annotations

from cys_core.domain.security.auth_models import AuthClaims


class TenantMismatchError(Exception):
    """Caller tenant_id does not match JWT organization claim."""

    def __init__(self, claimed: str, requested: str) -> None:
        self.claimed = claimed
        self.requested = requested
        super().__init__(f"tenant_mismatch: claimed={claimed!r} requested={requested!r}")


def resolve_organization_id(auth: AuthClaims | None, *, default: str = "default") -> str:
    """Organization id from JWT claims, or default when auth is disabled."""
    if auth is None:
        return default
    org = (auth.organization_id or "").strip()
    return org or default


def require_tenant_match(
    auth: AuthClaims | None,
    tenant_id: str,
    *,
    enforce: bool = True,
) -> str:
    """
    Bind request tenant_id to JWT organization_id.

    When auth is None (AUTH_ENABLED=0), returns tenant_id unchanged.
    When enforce and auth present: reject mismatch unless organization_id empty
    (legacy tokens) — empty org allows any tenant for backward compat until IdP
    always emits org claim.
    """
    requested = (tenant_id or "default").strip() or "default"
    if auth is None or not enforce:
        return requested
    claimed = (auth.organization_id or "").strip()
    if not claimed:
        return requested
    if claimed != requested:
        raise TenantMismatchError(claimed=claimed, requested=requested)
    return claimed
