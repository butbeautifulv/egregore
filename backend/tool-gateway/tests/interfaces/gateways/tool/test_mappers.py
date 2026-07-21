from __future__ import annotations

import pytest

from cys_core.domain.tools.models import ToolInvokeResult
from interfaces.gateways.tool.mappers import to_command, to_response
from interfaces.gateways.tool.models import ToolInvokeRequest


@pytest.mark.unit
def test_to_command_carries_approval_token_from_the_wire():
    """Regression: a live end-to-end HITL proof (docs/MSP_BACKLOG.md §61) found this field
    silently dropped — ToolInvokeRequest/to_command predate §58's approval_token field and
    were never updated alongside cys_core.domain.tools.models, so a real approval-retry
    request would have its token discarded before InvokeTool ever saw it."""
    request = ToolInvokeRequest(
        tool_name="python_sandbox",
        args={"code": "print(1)"},
        persona="gaia_solver",
        sandbox_id="sb-1",
        approval_token="tok-abc",
    )
    command = to_command(request)
    assert command.approval_token == "tok-abc"


@pytest.mark.unit
def test_to_response_carries_hitl_fields_back_over_the_wire():
    """Regression: same bug, response side — ToolInvokeResponse predates §58's
    hitl_required/risk_level/approval_token fields on ToolInvokeResult, so a real gateway
    refusal was silently flattened to a generic error with no way for the caller to tell a
    HITL pause apart from any other failure."""
    result = ToolInvokeResult(
        success=False,
        tool_name="python_sandbox",
        error="hitl_required",
        hitl_required=True,
        risk_level="high",
        approval_token="tok-xyz",
    )
    response = to_response(result)
    assert response.hitl_required is True
    assert response.risk_level == "high"
    assert response.approval_token == "tok-xyz"
