from __future__ import annotations

import pytest
from pydantic import ValidationError

from bootstrap.settings import Settings


@pytest.mark.unit
def test_settings_dev_defaults_leave_auth_disabled() -> None:
    settings = Settings(STAGE="dev")
    assert settings.auth_enabled is False


@pytest.mark.unit
def test_settings_rejects_invalid_stage() -> None:
    with pytest.raises(ValidationError, match="invalid stage"):
        Settings(STAGE="bogus")


@pytest.mark.unit
def test_settings_auth_enabled_requires_shared_secret() -> None:
    with pytest.raises(ValidationError, match="MODEL_GATEWAY_SHARED_SECRET"):
        Settings(STAGE="dev", MODEL_GATEWAY_AUTH_ENABLED=True, MODEL_GATEWAY_SHARED_SECRET="")


@pytest.mark.unit
def test_settings_prod_rejects_auth_disabled() -> None:
    """docs/MSP_BACKLOG.md §11.2's prod-guard pattern, applied to
    model-gateway: api/worker/tool-gateway all refuse to start at STAGE=prod with
    their own off-by-default auth toggle disabled — this package's settings.py
    never got the same guard when it was built in §29."""
    with pytest.raises(ValidationError, match="MODEL_GATEWAY_AUTH_ENABLED"):
        Settings(STAGE="prod", MODEL_GATEWAY_AUTH_ENABLED=False)


@pytest.mark.unit
def test_settings_prod_allows_insecure_auth_with_explicit_override() -> None:
    settings = Settings(STAGE="prod", MODEL_GATEWAY_AUTH_ENABLED=False, ALLOW_INSECURE_PROD_AUTH=True)
    assert settings.allow_insecure_prod_auth is True


@pytest.mark.unit
def test_settings_prod_allows_auth_enabled_with_secret() -> None:
    settings = Settings(
        STAGE="prod", MODEL_GATEWAY_AUTH_ENABLED=True, MODEL_GATEWAY_SHARED_SECRET="secret"
    )
    assert settings.auth_enabled is True
