from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.application.use_cases.run_worker_job import RunWorkerJob
from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    record_tool_success,
    record_tool_output,
)
from cys_core.domain.policy.defaults import PERSONA_BUDGETS
from cys_core.domain.workers.models import WorkerJob
from tests.application.workers.factory import build_run_worker_job_for_tests


@pytest.mark.unit
@pytest.mark.asyncio
async def test_try_salvage_partial_resolves_investigation_id_before_defn() -> None:
    """Regression: investigation_id was used before assignment (cc56 intel-bus UnboundLocalError)."""
    job_id = "intel-bus-salvage-cc56"
    clear_tool_execution_count(job_id)
    record_tool_output(job_id, "enrich_ioc", "IOC 192.168.1.50 marked malicious in TI feed")
    job = WorkerJob(
        job_id=job_id,
        event_id="evt-salvage",
        persona="intel",
        correlation_id="eng-salvage-cc56",
        payload={"phase": "specialist"},
    )
    job_finalizer = SimpleNamespace(
        mark_persona_completed=lambda _job: None,
        mark_success=AsyncMock(),
    )
    registry = SimpleNamespace(
        get=lambda _name: SimpleNamespace(
            schema_name="IntelFinding",
            tools=[],
            skills=[],
            bus_recipients=[],
            role="worker",
        )
    )
    runner = build_run_worker_job_for_tests(
        job_finalizer=job_finalizer,
        registry=registry,
        schema_registry=SimpleNamespace(get=lambda _name: None),
    )

    result = await runner.try_salvage_partial(
        job,
        "sess-salvage",
        {},
        reason="recursion_limit_exhausted",
    )

    assert result is not None
    assert result.success is True
    assert result.finding is not None
    assert "192.168.1.50" in result.finding.get("iocs", [])
    job_finalizer.mark_success.assert_awaited_once()
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_persona_budget_max_tool_calls_soc_intel() -> None:
    assert PERSONA_BUDGETS["soc"].max_tool_calls == 6
    assert PERSONA_BUDGETS["intel"].max_tool_calls == 6


@pytest.mark.unit
def test_retry_nudge_intel_after_enrich_ioc() -> None:
    jid = "intel-job-nudge"
    clear_tool_execution_count(jid)
    record_tool_success(jid, "enrich_ioc")
    job = SimpleNamespace(job_id=jid, persona="intel")
    run = RunWorkerJob.__new__(RunWorkerJob)
    nudge = run._retry_nudge(
        job,
        "base prompt",
        attempt=0,
        planned_tool_calls=False,
        tools_executed=2,
    )
    assert nudge is not None
    assert "IntelFinding" in nudge
    clear_tool_execution_count(jid)


@pytest.mark.unit
def test_retry_nudge_soc_after_six_tools() -> None:
    jid = "soc-job-nudge"
    clear_tool_execution_count(jid)
    job = SimpleNamespace(job_id=jid, persona="soc")
    run = RunWorkerJob.__new__(RunWorkerJob)
    nudge = run._retry_nudge(
        job,
        "base prompt",
        attempt=0,
        planned_tool_calls=False,
        tools_executed=6,
    )
    assert nudge is not None
    assert "summary" in nudge.lower()
    clear_tool_execution_count(jid)


@pytest.mark.unit
def test_retry_nudge_consultant_after_load_skill() -> None:
    jid = "consultant-job-nudge"
    clear_tool_execution_count(jid)
    record_tool_success(jid, "load_skill")
    job = SimpleNamespace(job_id=jid, persona="consultant")
    run = RunWorkerJob.__new__(RunWorkerJob)
    nudge = run._retry_nudge(
        job,
        "base prompt",
        attempt=0,
        planned_tool_calls=False,
        tools_executed=2,
    )
    assert nudge is not None
    assert "ConsultantFinding" in nudge
    clear_tool_execution_count(jid)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_try_salvage_partial_consultant_recursion() -> None:
    job_id = "consultant-salvage-recursion"
    clear_tool_execution_count(job_id)
    record_tool_output(job_id, "playbook_search", '{"count":1,"skills":[]}')
    record_tool_output(job_id, "load_skill", "veil-knowledge loaded")
    job = WorkerJob(
        job_id=job_id,
        event_id="evt-consultant-salvage",
        persona="consultant",
        correlation_id="eng-consultant-salvage",
        payload={"goal": "Как настроить WAF?"},
    )
    job_finalizer = SimpleNamespace(
        mark_persona_completed=lambda _job: None,
        mark_success=AsyncMock(),
    )
    registry = SimpleNamespace(
        get=lambda _name: SimpleNamespace(
            schema_name="ConsultantFinding",
            tools=[],
            skills=[],
            bus_recipients=[],
            role="worker",
        )
    )
    runner = build_run_worker_job_for_tests(
        job_finalizer=job_finalizer,
        registry=registry,
        schema_registry=SimpleNamespace(get=lambda _name: None),
    )

    result = await runner.try_salvage_partial(
        job,
        "sess-consultant-salvage",
        {},
        reason="recursion_limit_exhausted",
    )

    assert result is not None
    assert result.success is True
    assert result.finding is not None
    assert result.finding.get("topic") == "Как настроить WAF?"
    assert len(result.finding.get("recommendations", [])) >= 2
    job_finalizer.mark_success.assert_awaited_once()
    clear_tool_execution_count(job_id)
