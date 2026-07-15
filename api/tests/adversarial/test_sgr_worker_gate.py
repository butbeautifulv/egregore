from __future__ import annotations

import pytest
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest

from cys_core.application.reasoning.sgr_policy import ResolvedSgrPolicy
from cys_core.domain.reasoning.sgr_models import SchemaGuidedReasoningStep
from cys_core.middleware.sgr_reasoning_middleware import SchemaGuidedReasoningMiddleware
from cys_core.middleware.sgr_one_tool_middleware import SgrOneToolMiddleware
from cys_core.middleware.sgr_session import SgrSessionState


@pytest.mark.unit
def test_worker_sgr_stack_blocks_siem_without_reasoning():
    session = SgrSessionState()
    reasoning_mw = SchemaGuidedReasoningMiddleware(
        policy=ResolvedSgrPolicy(enabled=True, mode="sgr_hybrid", require_before_action=True),
        session=session,
    )
    one_tool_mw = SgrOneToolMiddleware(session=session)
    request = ToolCallRequest(
        tool_call={"name": "query_siem_readonly", "id": "1", "args": {}},
        tool=None,  # type: ignore[arg-type]
        state={},
        runtime=None,  # type: ignore[arg-type]
    )

    def handler(_req):
        return ToolMessage(content="ok", tool_call_id="1")

    blocked = reasoning_mw.wrap_tool_call(request, handler)
    assert isinstance(blocked, ToolMessage)
    assert blocked.status == "error"


@pytest.mark.unit
def test_worker_sgr_stack_allows_reasoning_then_one_action():
    session = SgrSessionState()
    session.mark_reasoning(
        SchemaGuidedReasoningStep(
            reasoning_steps=["a", "b"],
            current_situation="x",
            plan_status="y",
            task_completed=False,
        )
    )
    reasoning_mw = SchemaGuidedReasoningMiddleware(
        policy=ResolvedSgrPolicy(enabled=True, mode="sgr_hybrid", require_before_action=True),
        session=session,
    )
    one_tool_mw = SgrOneToolMiddleware(session=session)
    request = ToolCallRequest(
        tool_call={"name": "query_siem_readonly", "id": "1", "args": {}},
        tool=None,  # type: ignore[arg-type]
        state={},
        runtime=None,  # type: ignore[arg-type]
    )

    def handler(_req):
        return ToolMessage(content="ok", tool_call_id="1")

    passed = reasoning_mw.wrap_tool_call(request, lambda r: one_tool_mw.wrap_tool_call(r, handler))
    assert isinstance(passed, ToolMessage)
    assert passed.content == "ok"
