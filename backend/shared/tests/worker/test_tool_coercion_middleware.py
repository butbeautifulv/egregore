from __future__ import annotations

import json

import pytest
import structlog
from langchain_core.messages import ToolMessage

from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    get_tool_call_count,
    tool_succeeded,
)
from cys_core.middleware.tool_coercion_middleware import ToolCoercionMiddleware, _tool_result_ok


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


@pytest.mark.unit
def test_record_success_tracks_load_skill() -> None:
    """Regression: load_skill must be recorded as succeeded so the consultant
    ladder's "block everything after load_skill" gate can ever fire."""
    job_id = "job-coercion-load-skill"
    clear_tool_execution_count(job_id)
    structlog.contextvars.bind_contextvars(job_id=job_id)
    middleware = ToolCoercionMiddleware()
    result = ToolMessage(content=json.dumps({"success": True, "content": "skill loaded"}), tool_call_id="call-1")
    middleware._record_success("load_skill", result)
    assert tool_succeeded(job_id, "load_skill") is True
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_record_call_counter_is_unbounded_across_many_calls() -> None:
    """Regression: the per-tool-name call counter used for ladder budgets must
    not be capped by tool_stored_outputs_max the way the preview cache is."""
    job_id = "job-coercion-call-count"
    clear_tool_execution_count(job_id)
    structlog.contextvars.bind_contextvars(job_id=job_id)
    middleware = ToolCoercionMiddleware()
    for _ in range(10):
        middleware._record("playbook_search")
    assert get_tool_call_count(job_id, "playbook_search") == 10
    clear_tool_execution_count(job_id)
