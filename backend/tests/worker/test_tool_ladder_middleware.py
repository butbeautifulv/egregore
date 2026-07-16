from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import structlog
from langchain_core.messages import ToolMessage

from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    record_evidence_manifest,
    record_persona_manifest,
    record_siem_drilldown,
    record_tool_success,
    record_veil_tool,
    seed_job_from_persona_manifest,
)
from cys_core.domain.evidence.models import DataGap, EvidenceManifest, Observation
from cys_core.middleware.tool_ladder_middleware import ToolLadderMiddleware


def _request(tool_name: str, job_id: str = "job-ladder") -> SimpleNamespace:
    structlog.contextvars.bind_contextvars(job_id=job_id)
    return SimpleNamespace(tool_call={"name": tool_name, "args": {}, "id": "call-1", "type": "tool_call"})


@pytest.mark.unit
def test_tool_ladder_blocks_siem_after_investigate_incident() -> None:
    clear_tool_execution_count("job-ladder")
    record_tool_success("job-ladder", "investigate_incident")
    middleware = ToolLadderMiddleware(persona="soc")
    blocked = middleware._check(_request("search_events"))
    assert blocked is not None
    assert isinstance(blocked, ToolMessage)
    assert "SIEM ladder complete" in str(blocked.content)
    allowed = middleware._check(_request("get_event_by_uuid"))
    assert allowed is None
    clear_tool_execution_count("job-ladder")


@pytest.mark.unit
def test_tool_ladder_blocks_extra_veil_tools() -> None:
    clear_tool_execution_count("job-veil")
    record_veil_tool("job-veil")
    record_veil_tool("job-veil")
    middleware = ToolLadderMiddleware(persona="intel")
    blocked = middleware._check(_request("ti_search_in_category", job_id="job-veil"))
    assert blocked is not None
    assert "Veil tool budget exhausted" in str(blocked.content)
    clear_tool_execution_count("job-veil")


def _sparse_manifest() -> EvidenceManifest:
    return EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.5,
        observations=[
            Observation(
                obs_id="obs:host:ms-113",
                kind="host",
                value="ms-113.tpsgroup.ru",
                source_tool="investigate_incident",
                source_path="incident.targets",
            ),
        ],
        data_gaps=[
            DataGap(
                field="subject.process.cmdline",
                reason="not_in_siem",
                remediation="Collect EDR telemetry",
            ),
        ],
    )


@pytest.mark.unit
def test_tool_ladder_blocks_repeat_investigate_incident_sparse() -> None:
    job_id = "job-sparse-repeat"
    clear_tool_execution_count(job_id)
    record_tool_success(job_id, "investigate_incident")
    record_evidence_manifest(job_id, "investigate_incident", _sparse_manifest())
    middleware = ToolLadderMiddleware(persona="soc")
    blocked = middleware._check(_request("investigate_incident", job_id=job_id))
    assert blocked is not None
    assert "already completed" in str(blocked.content)
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_tool_ladder_allows_sparse_search_events_before_drilldown_exhausted() -> None:
    job_id = "job-sparse-drill"
    clear_tool_execution_count(job_id)
    record_tool_success(job_id, "investigate_incident")
    record_evidence_manifest(job_id, "investigate_incident", _sparse_manifest())
    middleware = ToolLadderMiddleware(persona="soc")
    allowed = middleware._check(_request("search_events", job_id=job_id))
    assert allowed is None
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_tool_ladder_blocks_search_events_when_drilldown_exhausted() -> None:
    job_id = "job-sparse-drill-exhausted"
    clear_tool_execution_count(job_id)
    record_tool_success(job_id, "investigate_incident")
    record_evidence_manifest(job_id, "investigate_incident", _sparse_manifest())
    for _ in range(2):
        record_siem_drilldown(job_id)
    middleware = ToolLadderMiddleware(persona="soc")
    blocked = middleware._check(_request("search_events", job_id=job_id))
    assert blocked is not None
    assert "SIEM ladder complete" in str(blocked.content)
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_tool_ladder_blocks_repeat_investigate_from_persona_manifest() -> None:
    job_id = "job-revision-bus"
    investigation_id = "eng-revision-manifest"
    clear_tool_execution_count(job_id)
    record_persona_manifest(investigation_id, "soc", _sparse_manifest())
    seed_job_from_persona_manifest(job_id, _sparse_manifest(), mark_siem_done=True)
    middleware = ToolLadderMiddleware(persona="soc")
    structlog.contextvars.bind_contextvars(job_id=job_id, correlation_id=investigation_id)
    blocked = middleware._check(_request("investigate_incident", job_id=job_id))
    assert blocked is not None
    assert "already completed" in str(blocked.content)
    allowed = middleware._check(_request("get_event_by_uuid", job_id=job_id))
    assert allowed is None
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_security_middleware_skips_budget_on_blocked_tool_result() -> None:
    from cys_core.domain.workers.job_budget import JobBudgetTracker
    from cys_core.middleware.security_middleware import SecurityMiddleware

    session_id = "sess-blocked-budget"
    JobBudgetTracker.configure(session_id, max_tokens=10_000, max_cost_usd=1.0, max_tool_calls=3)
    middleware = SecurityMiddleware(agent_id="soc", session_id=session_id)
    request = SimpleNamespace(tool_call={"name": "search_events", "args": {}, "id": "call-1"})
    blocked = ToolMessage(
        content="SIEM ladder complete after investigate_incident. Emit SocFinding JSON.",
        tool_call_id="call-1",
        status="error",
    )

    middleware.wrap_tool_call(request, lambda _req: blocked)
    state = JobBudgetTracker.get(session_id)
    assert state is not None
    assert state.tool_calls == 0
    JobBudgetTracker.clear(session_id)


@pytest.mark.unit
def test_one_tool_middleware_allows_two_soc_tools_before_investigate() -> None:
    from cys_core.middleware.one_tool_middleware import OneToolPerTurnMiddleware

    structlog.contextvars.bind_contextvars(job_id="job-soc-two", correlation_id="eng-soc-two")
    middleware = OneToolPerTurnMiddleware(persona="soc")
    request = SimpleNamespace(tool_call={"name": "investigate_incident", "args": {}, "id": "call-1"})
    handler = MagicMock(return_value=ToolMessage(content="ok", tool_call_id="call-1", status="success"))
    first = middleware.wrap_tool_call(request, handler)
    assert first.status != "error"
    request2 = SimpleNamespace(tool_call={"name": "get_event_by_uuid", "args": {}, "id": "call-2"})
    second = middleware.wrap_tool_call(request2, handler)
    assert second.status != "error"
    request3 = SimpleNamespace(tool_call={"name": "list_incident_events", "args": {}, "id": "call-3"})
    third = middleware.wrap_tool_call(request3, handler)
    assert isinstance(third, ToolMessage)
    assert "Only one tool call per turn" in str(third.content)


@pytest.mark.unit
def test_tool_ladder_blocks_load_skill_when_veil_budget_exhausted() -> None:
    job_id = "job-sparse-veil"
    clear_tool_execution_count(job_id)
    record_tool_success(job_id, "investigate_incident")
    record_evidence_manifest(job_id, "investigate_incident", _sparse_manifest())
    record_veil_tool(job_id)
    record_veil_tool(job_id)
    middleware = ToolLadderMiddleware(persona="soc")
    blocked = middleware._check(_request("load_skill", job_id=job_id))
    assert blocked is not None
    assert "SIEM/Veil ladder complete" in str(blocked.content)
    clear_tool_execution_count(job_id)
