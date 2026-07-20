from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from cys_core.domain.security.auth_models import AuthClaims
from interfaces.api.tenant_deps import TenantBound, require_tenant_match_http


@pytest.mark.unit
def test_tenant_bind_rejects_missing_organization_claim_by_default() -> None:
    """5-whys root cause fix (docs/MSP_BACKLOG.md §11.3/§13 Phase 9):
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


def _mock_request(*, method: str = "POST", json_side_effect: Exception) -> MagicMock:
    request = MagicMock()
    request.query_params.get.return_value = None
    request.method = method
    request.json = AsyncMock(side_effect=json_side_effect)
    return request


@pytest.mark.unit
async def test_tenant_bound_falls_back_to_default_on_malformed_json_body() -> None:
    """§27.6: only the intended JSON-decode-error case should fall back to 'default'."""
    request = _mock_request(json_side_effect=json.JSONDecodeError("bad json", "doc", 0))
    auth = AuthClaims(sub="alice", organization_id="default")

    result = await TenantBound()(request, auth)

    assert result == "default"


@pytest.mark.unit
async def test_tenant_bound_propagates_unexpected_errors_instead_of_silently_defaulting() -> None:
    """§27.6 root-cause fix: TenantBound() used to catch *any* exception while parsing the
    request body and silently fall back to 'default', not just the intended JSON-decode-error
    case. A body-read failure unrelated to malformed JSON (e.g. a broken stream) must now
    propagate instead of masquerading as a legitimate default-tenant request."""
    request = _mock_request(json_side_effect=RuntimeError("body stream broken"))
    auth = AuthClaims(sub="alice", organization_id="acme")

    with pytest.raises(RuntimeError):
        await TenantBound()(request, auth)
