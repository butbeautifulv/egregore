from __future__ import annotations

import pytest
from fastapi import HTTPException

from cys_core.domain.security.auth_models import AuthClaims
from interfaces.api.tenant_deps import require_tenant_match_http


@pytest.mark.unit
def test_tenant_bind_rejects_missing_organization_claim_by_default() -> None:
    """5-whys root cause fix (docs/MICROSERVICES_SPLIT_PLAN.md §11.3/§13 Phase 9):
    an empty organization_id claim used to silently trust the requested
    tenant_id unconditionally ('legacy tokens'). Default is now stricter —
    reject unless ALLOW_LEGACY_TENANT_TOKENS is explicitly set."""
    auth = AuthClaims(sub="alice", organization_id="")

    with pytest.raises(HTTPException) as exc_info:
        require_tenant_match_http(auth, "acme")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "MISSING_ORGANIZATION_CLAIM"


@pytest.mark.unit
def test_tenant_bind_allows_missing_organization_claim_with_explicit_flag(monkeypatch) -> None:
    from bootstrap.container import get_container

    monkeypatch.setattr(get_container().settings, "allow_legacy_tenant_tokens", True)
    auth = AuthClaims(sub="alice", organization_id="")

    assert require_tenant_match_http(auth, "acme") == "acme"


@pytest.mark.unit
def test_tenant_bind_accepts_matching_auth_claim() -> None:
    auth = AuthClaims(sub="alice", organization_id="acme")

    assert require_tenant_match_http(auth, "acme") == "acme"


@pytest.mark.unit
def test_tenant_bind_rejects_mismatched_auth_claim() -> None:
    auth = AuthClaims(sub="alice", organization_id="acme")

    with pytest.raises(HTTPException) as exc_info:
        require_tenant_match_http(auth, "other")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "TENANT_MISMATCH"


@pytest.mark.unit
def test_tenant_bind_allows_any_tenant_when_auth_disabled() -> None:
    assert require_tenant_match_http(None, "other") == "other"
