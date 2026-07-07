from __future__ import annotations

import json

import pytest
from langchain_core.messages import ToolMessage

from cys_core.middleware.tool_coercion_middleware import _tool_result_ok


@pytest.mark.unit
def test_tool_result_ok_rejects_success_false_json() -> None:
    result = ToolMessage(
        content=json.dumps({"success": False, "error": "technique_id is required"}),
        tool_call_id="call-1",
    )
    assert _tool_result_ok(result) is False


@pytest.mark.unit
def test_tool_result_ok_accepts_success_true_json() -> None:
    result = ToolMessage(
        content=json.dumps({"success": True, "content": {"count": 1}}),
        tool_call_id="call-1",
    )
    assert _tool_result_ok(result) is True
