from __future__ import annotations

import pytest
from fastapi import HTTPException

from cys_core.application.authz.service import AuthzService
from cys_core.domain.security.auth_models import AuthClaims
from cys_core.infrastructure.authz.noop import NoopAuthzPort
from interfaces.api.authz_helpers import require_workspace_relation


@pytest.mark.unit
def test_empty_workspace_denied_in_enforce(monkeypatch: pytest.MonkeyPatch) -> None:
    authz = AuthzService(NoopAuthzPort(), mode="enforce")
    from unittest.mock import MagicMock

    container = MagicMock()
    container.get_authz_service.return_value = authz
    monkeypatch.setattr("interfaces.api.authz_helpers.get_container", lambda: container)
    with pytest.raises(HTTPException):
        require_workspace_relation(AuthClaims(sub="u1"), None, "", "can_view")
