from __future__ import annotations

import pytest

from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.policy.defaults import DEFAULT_BUS_POLICY, ESCALATION_ONLY_PATHS
from cys_core.domain.security.agent_bus import SecureAgentBus


@pytest.mark.unit
def test_secure_agent_bus_uses_injected_policy():
    policy = ProfilePolicyPayload(
        breaker_failure_threshold=3,
        breaker_reset_seconds=120,
        bus_policy={"worker": ["critic"]},
        escalation_paths=[["soc", "redteam"]],
    )
    bus = SecureAgentBus(policy=policy)
    assert bus._breaker_threshold == 3
    assert bus._breaker_reset == 120
    assert bus._bus_policy == {"worker": ["critic"]}
    assert ("soc", "redteam") in bus._escalation_paths


@pytest.mark.unit
def test_secure_agent_bus_defaults_without_injection():
    bus = SecureAgentBus()
    assert bus._breaker_threshold == 5
    assert bus._bus_policy == dict(DEFAULT_BUS_POLICY)
    assert bus._escalation_paths == set(ESCALATION_ONLY_PATHS)
