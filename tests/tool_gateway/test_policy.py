from __future__ import annotations

import pytest

from interfaces.gateways.tool.models import ToolInvokeRequest
from interfaces.gateways.tool.policy import (
    ToolChainDepthExceeded,
    check_tool_chain,
    clear_all_chain_states,
    get_chain_state,
)


@pytest.mark.unit
def test_high_risk_chain_depth_limit(monkeypatch):
    clear_all_chain_states()
    monkeypatch.setattr("interfaces.gateways.tool.policy.settings.max_high_risk_tool_chain_depth", 2)
    req = ToolInvokeRequest(
        tool_name="run_active_scan",
        args={"target": "lab"},
        persona="redteam",
        sandbox_id="sandbox-1",
        job_id="job-chain",
    )
    check_tool_chain(req)
    check_tool_chain(req)
    with pytest.raises(ToolChainDepthExceeded):
        check_tool_chain(req)
    assert get_chain_state("job-chain").consecutive_high_risk == 2
    clear_all_chain_states()


@pytest.mark.unit
def test_low_risk_tool_resets_chain(monkeypatch):
    clear_all_chain_states()
    monkeypatch.setattr("interfaces.gateways.tool.policy.settings.max_high_risk_tool_chain_depth", 2)
    high = ToolInvokeRequest(
        tool_name="run_active_scan",
        args={},
        persona="redteam",
        sandbox_id="sandbox-1",
        job_id="job-reset",
    )
    low = ToolInvokeRequest(
        tool_name="parse_netflow",
        args={},
        persona="redteam",
        sandbox_id="sandbox-1",
        job_id="job-reset",
    )
    check_tool_chain(high)
    check_tool_chain(low)
    assert get_chain_state("job-reset").consecutive_high_risk == 0
    clear_all_chain_states()
