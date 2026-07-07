from __future__ import annotations

from types import SimpleNamespace

import pytest

from cys_core.application.use_cases.run_worker_job import RunWorkerJob
from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    record_tool_success,
)
from cys_core.domain.policy.defaults import PERSONA_BUDGETS


@pytest.mark.unit
def test_persona_budget_max_tool_calls_soc_intel() -> None:
    assert PERSONA_BUDGETS["soc"].max_tool_calls == 8
    assert PERSONA_BUDGETS["intel"].max_tool_calls == 8


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
