from __future__ import annotations

import pytest

from cys_core.application.datasources.authz_policy import authorize_datasource_access, persona_roles
from cys_core.application.datasources.policy_resolver import datasource_policy_for
from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.datasources.authz import AuthzRequest
from cys_core.domain.datasources.models import DataSource, DataSourceCapability
from cys_core.domain.security.data_classification import DataClassification


def _req(
    *,
    persona: str = "consultant",
    profile_id: str = "general-assistant",
    datasource_id: str = "ds-1",
    capability: DataSourceCapability = DataSourceCapability.GET,
) -> AuthzRequest:
    return AuthzRequest(
        persona=persona,
        profile_id=profile_id,
        datasource_id=datasource_id,
        capability=capability,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("persona", "profile_id", "capability", "classification", "source_caps", "policy", "expected_allowed", "expected_reason"),
    [
        ("consultant", "general-assistant", DataSourceCapability.GET, DataClassification.INTERNAL, [DataSourceCapability.GET], None, True, "allowed"),
        ("consultant", "general-assistant", DataSourceCapability.MUTATE, DataClassification.INTERNAL, [DataSourceCapability.GET], None, False, "capability_not_granted"),
        ("consultant", "general-assistant", DataSourceCapability.GET, DataClassification.RESTRICTED, [DataSourceCapability.GET], None, False, "classification_denied"),
        ("critic", DEFAULT_PROFILE_ID, DataSourceCapability.GET, DataClassification.INTERNAL, [DataSourceCapability.GET], None, True, "allowed"),
        (
            "consultant",
            "general-assistant",
            DataSourceCapability.GET,
            DataClassification.INTERNAL,
            [DataSourceCapability.GET],
            ProfilePolicyPayload(datasource_allowlist={"general-assistant": ["web-cache"]}),
            False,
            "not_in_profile_allowlist",
        ),
        (
            "consultant",
            "general-assistant",
            DataSourceCapability.GET,
            DataClassification.INTERNAL,
            [DataSourceCapability.GET],
            ProfilePolicyPayload(
                datasource_allowlist={"general-assistant": ["web-cache", "docs-index"]},
                persona_datasource_allowlist={"general-assistant": {"consultant": ["docs-index"]}},
            ),
            False,
            "not_in_persona_allowlist",
        ),
        (
            "soc",
            DEFAULT_PROFILE_ID,
            DataSourceCapability.QUERY,
            DataClassification.INTERNAL,
            [DataSourceCapability.GET],
            ProfilePolicyPayload(
                datasource_capability_grants={DEFAULT_PROFILE_ID: {"siem-readonly": ["query"]}},
            ),
            True,
            "allowed",
        ),
    ],
    ids=[
        "get_default_allow",
        "mutate_denied_without_grant",
        "classification_denied",
        "critic_get_allow",
        "profile_allowlist_deny",
        "persona_allowlist_deny",
        "capability_grant_override",
    ],
)
def test_authz_matrix(
    persona: str,
    profile_id: str,
    capability: DataSourceCapability,
    classification: DataClassification,
    source_caps: list[DataSourceCapability],
    policy: ProfilePolicyPayload | None,
    expected_allowed: bool,
    expected_reason: str,
) -> None:
    source_id = "ds-unknown"
    if policy and policy.persona_datasource_allowlist.get(profile_id, {}).get(persona) and not expected_allowed:
        source_id = "web-cache"
    elif expected_allowed and capability == DataSourceCapability.QUERY and profile_id == DEFAULT_PROFILE_ID:
        source_id = "siem-readonly"
    elif policy and policy.datasource_capability_grants.get(profile_id):
        source_id = next(iter(policy.datasource_capability_grants[profile_id]))
    elif expected_allowed and policy and policy.datasource_allowlist.get(profile_id):
        source_id = policy.datasource_allowlist[profile_id][0]
    source = DataSource(
        id=source_id,
        type="test",
        classification=classification,
        capabilities=source_caps,
        allowed_roles=["reader", "worker", "control"],
    )
    decision = authorize_datasource_access(
        _req(persona=persona, profile_id=profile_id, datasource_id=source_id, capability=capability),
        source,
        policy=policy,
    )
    assert decision.allowed is expected_allowed
    assert decision.reason == expected_reason


@pytest.mark.unit
def test_product_policy_grants_siem_query_for_soc() -> None:
    policy = datasource_policy_for(DEFAULT_PROFILE_ID)
    source = DataSource(id="siem-readonly", type="siem", capabilities=[DataSourceCapability.GET])
    decision = authorize_datasource_access(
        _req(persona="soc", profile_id=DEFAULT_PROFILE_ID, datasource_id="siem-readonly", capability=DataSourceCapability.QUERY),
        source,
        policy=policy,
    )
    assert decision.allowed is True


@pytest.mark.unit
def test_product_policy_general_assistant_allowlist() -> None:
    policy = datasource_policy_for("general-assistant")
    source = DataSource(id="web-cache", type="web", capabilities=[DataSourceCapability.GET])
    allowed = authorize_datasource_access(
        _req(datasource_id="web-cache", capability=DataSourceCapability.GET),
        source,
        policy=policy,
    )
    denied = authorize_datasource_access(
        _req(datasource_id="siem-readonly", capability=DataSourceCapability.GET),
        source,
        policy=policy,
    )
    assert allowed.allowed is True
    assert denied.allowed is False
    assert denied.reason == "not_in_profile_allowlist"


@pytest.mark.unit
def test_role_denied_when_not_in_allowed_roles() -> None:
    source = DataSource(
        id="ds-ops",
        type="vault",
        allowed_roles=["admin"],
        capabilities=[DataSourceCapability.GET],
    )
    decision = authorize_datasource_access(
        _req(persona="consultant", profile_id="general-assistant"),
        source,
    )
    assert decision.allowed is False
    assert decision.reason == "role_not_allowed"


@pytest.mark.unit
def test_persona_roles_matrix() -> None:
    assert "control" in persona_roles("critic")
    assert "control" not in persona_roles("consultant")
