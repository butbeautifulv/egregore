from __future__ import annotations

import pytest

from cys_core.domain.catalog.models import AnomalyPolicy
from cys_core.security.monitor import AgentMonitor


@pytest.mark.unit
def test_monitor_uses_injected_anomaly_policy():
    policy = AnomalyPolicy(tool_calls_per_minute=1, injection_attempts=0)
    monitor = AgentMonitor("agent", anomaly_policy=policy)
    assert monitor._thresholds["tool_calls_per_minute"] == 1
    assert monitor._thresholds["injection_attempts"] == 0
