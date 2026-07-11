from __future__ import annotations

import pytest

from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus


@pytest.mark.unit
def test_agent_bus_preserves_structural_correlation_id():
    bus = SecureAgentBus()
    bus.register_agent("soc", AgentTrustLevel.INTERNAL, ["critic"])
    bus.register_agent("critic", AgentTrustLevel.PRIVILEGED, ["soc", "intel"])

    engagement_id = "eng-deadbeefcafe"
    payload = {
        "correlation_id": engagement_id,
        "tenant_id": "default",
        "event_id": engagement_id,
        "data": {"summary": "suspicious login from 10.0.0.1"},
    }
    envelope = bus.send_message("soc", "critic", "finding", payload)
    received = bus.receive_message("critic", envelope)

    assert received["correlation_id"] == engagement_id
    assert received["tenant_id"] == "default"
    assert "USER_DATA_TO_PROCESS" not in received["correlation_id"]
    assert "USER_DATA_TO_PROCESS" in received["data"]["summary"]
