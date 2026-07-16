"""Shared tenant / organization binding for AuthN (ADR-005)."""

from __future__ import annotations

import structlog

from cys_core.domain.security.auth_models import AuthClaims

logger = structlog.get_logger(__name__)


class TenantMismatchError(Exception):
    """Caller tenant_id does not match JWT organization claim."""

    def __init__(self, claimed: str, requested: str) -> None:
        self.claimed = claimed
        self.requested = requested
        super().__init__(f"tenant_mismatch: claimed={claimed!r} requested={requested!r}")


class MissingOrganizationClaimError(Exception):
    """JWT has no organization_id claim and legacy-token fallback is disabled."""

    def __init__(self, requested: str) -> None:
        self.requested = requested
        super().__init__(f"missing_organization_claim: requested={requested!r}")


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
    allow_legacy_tokens: bool = False,
) -> str:
    """
    Bind request tenant_id to JWT organization_id.

    When auth is None (AUTH_ENABLED=0), returns tenant_id unchanged.
    When enforce and auth present: reject mismatch. A missing organization_id
    claim (docs/MICROSERVICES_SPLIT_PLAN.md §11.3) rejects the request unless
    ``allow_legacy_tokens`` is explicitly set — that flag exists only for a
    deliberate, temporary migration window, not as permanent behavior; every
    time it's exercised, that's logged so an operator can tell whether it's
    still safe to remove.
    """
    requested = (tenant_id or "default").strip() or "default"
    if auth is None or not enforce:
        return requested
    claimed = (auth.organization_id or "").strip()
    if not claimed:
        if not allow_legacy_tokens:
            raise MissingOrganizationClaimError(requested=requested)
        logger.warning("tenant_bind_fallback_used", requested_tenant_id=requested)
        return requested
    if claimed != requested:
        raise TenantMismatchError(claimed=claimed, requested=requested)
    return claimed
