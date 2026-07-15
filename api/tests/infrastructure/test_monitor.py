from __future__ import annotations

import pytest


@pytest.mark.unit
def test_monitor_logging_redaction_and_anomaly(monkeypatch):
    from cys_core.security.monitor import AgentMonitor

    monitor = AgentMonitor("agent")
    monkeypatch.setitem(monitor._thresholds, "tool_calls_per_minute", 1)

    monitor.log_tool_call(
        "session",
        "tool",
        {"password": "secret", "nested": [{"token": "abc"}]},
        {"status": "ok"},
        user_id="user",
    )
    monitor.log_tool_call("session", "tool", {"safe": True}, {}, user_id="user")
    monitor.log_security_event("session", "custom", "INFO", {"detail": "x"})

    first = monitor.events[0]
    assert first.details["parameters"]["password"] == "***REDACTED***"
    assert first.details["parameters"]["nested"][0]["token"] == "***REDACTED***"
    assert any(event.event_type == "anomaly_detected" for event in monitor.events)
    assert monitor.events[-1].event_type == "custom"
