from __future__ import annotations

from types import SimpleNamespace

import pytest
import structlog
from langchain_core.messages import ToolMessage

from cys_core.application.workers.tool_execution_tracker import clear_tool_execution_count
from cys_core.middleware.tool_dedup_middleware import ToolDedupMiddleware, clear_tool_dedup


def _request(tool_name: str, args: dict | None = None, job_id: str = "job-dedup") -> SimpleNamespace:
    structlog.contextvars.bind_contextvars(job_id=job_id)
    return SimpleNamespace(
        tool_call={"name": tool_name, "args": args or {"incident_id": "INC-1"}, "id": "call-1", "type": "tool_call"}
    )


@pytest.mark.unit
def test_tool_dedup_blocks_third_identical_call() -> None:
    clear_tool_dedup("job-dedup")
    middleware = ToolDedupMiddleware(persona="soc")
    handler = lambda req: ToolMessage(content="ok", tool_call_id="call-1")
    assert middleware.wrap_tool_call(_request("investigate_incident"), handler).content == "ok"
    assert middleware.wrap_tool_call(_request("investigate_incident"), handler).content == "ok"
    blocked = middleware.wrap_tool_call(_request("investigate_incident"), handler)
    assert isinstance(blocked, ToolMessage)
    assert "Duplicate tool call blocked" in str(blocked.content)
    clear_tool_dedup("job-dedup")


@pytest.mark.unit
def test_tool_dedup_skips_consultant() -> None:
    clear_tool_dedup("job-dedup")
    middleware = ToolDedupMiddleware(persona="consultant")
    blocked = middleware._check(_request("playbook_search", {"query": "phishing"}))
    assert blocked is None
    clear_tool_dedup("job-dedup")
