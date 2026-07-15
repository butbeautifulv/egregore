from __future__ import annotations

import pytest

from interfaces.api.deps import api_actor


@pytest.mark.unit
def test_api_actor_from_claims():
    from cys_core.domain.security.auth_models import AuthClaims

    assert api_actor(AuthClaims(sub="user-123", roles=("egregore-operator",))) == "user-123"
    assert api_actor(None) == "api"
