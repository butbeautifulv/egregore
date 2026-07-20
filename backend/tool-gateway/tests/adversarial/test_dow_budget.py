"""Abuse case: DoW — job killed when token/cost/tool-call budget exceeded."""

import pytest

from cys_core.domain.workers.job_budget import JobBudgetTracker
from interfaces.gateways.tool.policy import clear_all_chain_states
from tests.tool_gateway.gateway_client import GatewayTestClient


@pytest.mark.adversarial
def test_gateway_blocks_high_risk_tool_chain(monkeypatch):
    import bootstrap.container as container_mod
    from bootstrap.settings import Settings

    clear_all_chain_states()
    JobBudgetTracker.clear_all()
    container_mod._container = None
    # Pydantic-settings loads .env after kwargs — model_copy is required to override depth.
    monkeypatch.setattr(
        container_mod,
        "get_settings",
        lambda: Settings().model_copy(update={"max_high_risk_tool_chain_depth": 1}),
    )

    client = GatewayTestClient()
    body = {
        "tool_name": "run_active_scan",
        "args": {"target": "lab"},
        "persona": "redteam",
        "sandbox_id": "sandbox-dow",
        "job_id": "job-dow",
    }
    assert client.post("/invoke", json=body).json()["success"] is True
    blocked = client.post("/invoke", json=body).json()
    assert blocked["success"] is False
    assert "chain depth" in blocked["error"].lower()
    clear_all_chain_states()

# test_middleware_blocks_tool_call_budget (worker's copy) tested
# cys_core.middleware.security_middleware.SecurityMiddleware — the in-process
# LangGraph agent loop's own tool-call budget enforcement, a separate
# mechanism from this gateway's check_tool_chain/ToolChainPolicy above and
# not part of this package (cys_core/middleware/ deleted, see
# docs/MSP_BACKLOG.md §21.6). No equivalent here.
