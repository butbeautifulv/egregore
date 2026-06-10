"""Abuse case: multi-agent chaining — compromised agent cannot exceed trust boundary."""

import pytest

from cys_core.security.agent_bus import SecurityViolation


def test_signed_message_roundtrip(agent_bus):
    msg = agent_bus.send_message("network", "critic", "finding", {"summary": "beaconing"})
    payload = agent_bus.receive_message("critic", msg)
    assert payload["summary"] == "beaconing"


def test_tampered_signature_rejected(agent_bus):
    msg = agent_bus.send_message("network", "critic", "finding", {"summary": "ok"})
    msg["signature"] = "tampered"
    with pytest.raises(SecurityViolation, match="Invalid message signature"):
        agent_bus.receive_message("critic", msg)


def test_circuit_breaker_opens_after_failures(agent_bus):
    for _ in range(5):
        agent_bus.record_agent_failure("network")
    with pytest.raises(SecurityViolation, match="circuit breaker"):
        agent_bus.send_message("network", "critic", "finding", {"x": 1})
