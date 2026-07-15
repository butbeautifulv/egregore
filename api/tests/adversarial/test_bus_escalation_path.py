"""Abuse case: compromised soc cannot message privileged redteam except via critic-approved escalation."""

from __future__ import annotations

import pytest

from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus
from cys_core.domain.security.exceptions import SecurityViolation


@pytest.fixture
def production_bus():
    bus = SecureAgentBus(signing_key=b"prod-bus-key")
    bus.register_agent("soc", AgentTrustLevel.INTERNAL, ["network", "critic", "coordinator", "redteam"])
    bus.register_agent("network", AgentTrustLevel.INTERNAL, ["critic", "redteam"])
    bus.register_agent("redteam", AgentTrustLevel.PRIVILEGED, ["critic"])
    return bus


@pytest.mark.adversarial
def test_soc_direct_redteam_finding_blocked(production_bus):
    with pytest.raises(SecurityViolation, match="critic-approved escalation"):
        production_bus.send_message("soc", "redteam", "finding", {"summary": "pwned"})


@pytest.mark.adversarial
def test_network_direct_redteam_blocked(production_bus):
    with pytest.raises(SecurityViolation, match="critic-approved escalation"):
        production_bus.send_message("network", "redteam", "finding", {"summary": "beacon"})


@pytest.mark.adversarial
def test_critic_approved_escalation_allowed(production_bus):
    envelope = production_bus.send_message(
        "soc",
        "redteam",
        "escalation",
        {"critic_approved": True, "event_id": "evt-1"},
    )
    assert envelope["type"] == "escalation"
