"""Abuse case: privilege escalation — low-trust sessions cannot reach privileged tools."""

import pytest

from cys_core.security.agent_bus import SecurityViolation


def test_untrusted_cannot_message_privileged_recipient(agent_bus):
    with pytest.raises(SecurityViolation, match="not authorized"):
        agent_bus.send_message("untrusted", "report", "finding", {"data": "x"})


def test_high_risk_tool_classified():
    from cys_core.security.risk import RiskLevel, classify_tool_risk

    assert classify_tool_risk("execute_command") == RiskLevel.CRITICAL
    assert classify_tool_risk("parse_netflow") == RiskLevel.LOW
