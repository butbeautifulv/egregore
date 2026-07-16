from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.invoke_tool import InvokeTool
from cys_core.domain.tools.models import ToolInvokeCommand, ToolInvokeResult
from cys_core.infrastructure.tools.local_gateway import LocalToolExecutionGateway


@pytest.mark.unit
def test_local_gateway_delegates_to_invoke_tool():
    invoke = MagicMock(spec=InvokeTool)
    invoke.execute.return_value = ToolInvokeResult(
        success=True,
        tool_name="rag_query",
        data={"status": "simulated", "note": "demo"},
        sanitized_payload="{}",
    )
    gateway = LocalToolExecutionGateway(invoke)
    command = ToolInvokeCommand(
        tool_name="rag_query",
        args={"query": "x"},
        persona="soc",
        sandbox_id="sb-1",
    )
    result = gateway.invoke(command)
    invoke.execute.assert_called_once_with(command)
    assert result.success is True
    assert result.stub_result is not None
    assert result.stub_result.simulated is True
