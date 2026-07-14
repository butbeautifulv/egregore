from __future__ import annotations

from types import SimpleNamespace

import pytest
import structlog
from langchain_core.messages import ToolMessage

from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    record_tool_call,
    record_tool_output,
    record_tool_success,
)
from cys_core.middleware.tool_ladder_middleware import ToolLadderMiddleware


def _request(tool_name: str, job_id: str = "job-consultant") -> SimpleNamespace:
    structlog.contextvars.bind_contextvars(job_id=job_id)
    return SimpleNamespace(tool_call={"name": tool_name, "args": {}, "id": "call-1", "type": "tool_call"})


@pytest.mark.unit
def test_consultant_blocks_playbook_search_after_load_skill() -> None:
    job_id = "job-consultant-skill"
    clear_tool_execution_count(job_id)
    record_tool_success(job_id, "load_skill")
    middleware = ToolLadderMiddleware(persona="consultant")
    blocked = middleware._check(_request("playbook_search", job_id=job_id))
    assert blocked is not None
    assert isinstance(blocked, ToolMessage)
    assert "Consultant ladder complete" in str(blocked.content)
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_consultant_blocks_third_playbook_search() -> None:
    job_id = "job-consultant-playbook"
    clear_tool_execution_count(job_id)
    record_tool_call(job_id, "playbook_search")
    record_tool_call(job_id, "playbook_search")
    middleware = ToolLadderMiddleware(persona="consultant")
    blocked = middleware._check(_request("playbook_search", job_id=job_id))
    assert blocked is not None
    assert "Emit ConsultantFinding JSON" in str(blocked.content)
    allowed = middleware._check(_request("load_skill", job_id=job_id))
    assert allowed is None
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_consultant_allows_first_playbook_search() -> None:
    job_id = "job-consultant-allow"
    clear_tool_execution_count(job_id)
    middleware = ToolLadderMiddleware(persona="consultant")
    assert middleware._check(_request("playbook_search", job_id=job_id)) is None
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_consultant_playbook_budget_survives_output_window_eviction() -> None:
    """Regression: the playbook_search budget must be an unbounded per-tool
    counter, not derived from the trailing `tool_stored_outputs_max`-sized
    preview window — interleaving enough other tool calls used to silently
    evict the earlier playbook_search records and defeat the budget entirely
    (the real cause of consultant jobs looping to GRAPH_RECURSION_LIMIT)."""
    job_id = "job-consultant-window"
    clear_tool_execution_count(job_id)
    record_tool_call(job_id, "playbook_search")
    record_tool_call(job_id, "playbook_search")
    for _ in range(10):
        record_tool_output(job_id, "ti_list_categories", '{"count":1}')
    middleware = ToolLadderMiddleware(persona="consultant")
    blocked = middleware._check(_request("playbook_search", job_id=job_id))
    assert blocked is not None
    assert "Emit ConsultantFinding JSON" in str(blocked.content)
    clear_tool_execution_count(job_id)
