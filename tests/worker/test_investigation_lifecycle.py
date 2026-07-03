from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cys_core.domain.memory.models import InvestigationState
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus
from cys_core.infrastructure.memory.stores import InMemoryInvestigationStateStore
from cys_core.infrastructure.queue import InMemoryJobQueue


@pytest.mark.unit
def test_mark_persona_done_closes_consultant_only_plan() -> None:
    store = InMemoryInvestigationStateStore()
    store.upsert(
        InvestigationState(
            investigation_id="evt-ad",
            tenant_id="default",
            status="in_progress",
            planner_plan=["consultant"],
            planner_status="ok",
        )
    )
    store.mark_persona_done("default", "evt-ad", "consultant")
    state = store.get("default", "evt-ad")
    assert state is not None
    assert state.status == "closed"
    assert state.completed_personas == ["consultant"]


@pytest.mark.unit
def test_run_worker_job_notifies_after_terminal() -> None:
    from cys_core.application.use_cases.run_worker_job import RunWorkerJob

    store = InMemoryInvestigationStateStore()
    store.upsert(
        InvestigationState(
            investigation_id="evt-1",
            tenant_id="default",
            status="in_progress",
            planner_plan=["consultant"],
        )
    )
    notifier = MagicMock()
    job = WorkerJob(
        job_id="consultant-evt-1-abc",
        event_id="evt-1",
        persona="consultant",
        correlation_id="evt-1",
    )
    runner = RunWorkerJob(
        runtime=MagicMock(),
        registry=MagicMock(),
        bus=MagicMock(),
        sandbox=MagicMock(),
        transport=MagicMock(),
        queue=InMemoryJobQueue(),
        sanitizer=MagicMock(),
        guardrails=MagicMock(),
        job_store=MagicMock(),
        use_tool_gateway=False,
        resolve_mcp_tools=MagicMock(),
        resolve_legacy_tools=MagicMock(),
        make_load_skill_tool=MagicMock(),
        investigation_store=store,
        investigation_status_notifier=notifier,
    )
    runner._mark_persona_terminal(job)
    notifier.record_investigation_update.assert_called_once()
    payload = notifier.record_investigation_update.call_args.args[0]
    assert payload["investigation_id"] == "evt-1"
    assert payload["status"] == "closed"
    assert payload["completed_personas"] == ["consultant"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_job_timeout_marks_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    from interfaces.worker.orchestrator import WorkerOrchestrator

    monkeypatch.setenv("WORKER_JOB_TIMEOUT", "0.01")
    from bootstrap.settings import get_settings

    get_settings.cache_clear()

    job = WorkerJob(job_id="j1", event_id="evt-1", persona="consultant", correlation_id="evt-1")
    orch = WorkerOrchestrator(persona=None, runtime=MagicMock(), registry=MagicMock(), bus=MagicMock())
    orch.queue = InMemoryJobQueue()

    async def slow_execute(*_args, **_kwargs):
        await asyncio.sleep(1.0)
        return MagicMock(success=True)

    orch._run_worker_job.execute = slow_execute  # type: ignore[method-assign]
    orch.job_store = MagicMock()

    result = await orch.run_job(job)
    assert result.success is False
    assert result.error == "worker_job_timeout"
    orch.job_store.mark_failed.assert_called_once_with("j1")
