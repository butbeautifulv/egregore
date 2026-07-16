from __future__ import annotations

import pytest

from cys_core.application.datasources.authz_policy import authorize_datasource_access, persona_roles
from cys_core.domain.datasources.authz import AuthzRequest
from cys_core.domain.datasources.models import DataSource, DataSourceCapability
from cys_core.domain.security.data_classification import DataClassification


@pytest.mark.unit
def test_get_only_default_denies_mutate() -> None:
    source = DataSource(id="ds-1", type="sql")
    decision = authorize_datasource_access(
        AuthzRequest(
            persona="consultant",
            profile_id="cybersec-soc",
            datasource_id="ds-1",
            capability=DataSourceCapability.MUTATE,
        ),
        source,
    )
    assert decision.allowed is False
    assert decision.reason == "capability_not_granted"


@pytest.mark.unit
def test_persona_roles_include_control_for_critic() -> None:
    roles = persona_roles("critic", trust_level="internal")
    assert "control" in roles


@pytest.mark.unit
def test_classification_denied_for_restricted_source() -> None:
    source = DataSource(
        id="ds-restricted",
        type="vault",
        classification=DataClassification.RESTRICTED,
        capabilities=[DataSourceCapability.GET, DataSourceCapability.MUTATE],
    )
    decision = authorize_datasource_access(
        AuthzRequest(
            persona="consultant",
            profile_id="general-assistant",
            datasource_id="ds-restricted",
            capability=DataSourceCapability.GET,
        ),
        source,
    )
    assert decision.allowed is False
    assert decision.reason == "classification_denied"
