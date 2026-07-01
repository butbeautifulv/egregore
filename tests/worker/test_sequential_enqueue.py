from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.application.use_cases.run_worker_job import RunWorkerJob
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus, RunResult
from interfaces.worker.orchestrator import WorkerOrchestrator


@pytest.mark.unit
def test_sequential_enqueue_sets_dependencies():
    orch = WorkerOrchestrator(persona="soc")
    jobs = orch._jobs_for_routing(
        "evt-1",
        ["soc", "network", "compliance"],
        sequential=True,
    )
    assert jobs[0].depends_on_persona == ""
    assert jobs[1].depends_on_persona == "soc"
    assert jobs[2].depends_on_persona == "network"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_upstream_unblocks_sequential_downstream(monkeypatch):
    completed: list[str] = []

    class InvestigationStore:
        def mark_persona_done(self, tenant_id: str, investigation_id: str, persona: str) -> None:
            completed.append(persona)

        def get(self, tenant_id: str, investigation_id: str):
            from cys_core.domain.memory.models import InvestigationState

            return InvestigationState(
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                completed_personas=list(completed),
            )

    class JobStore:
        def upsert_running(self, *args, **kwargs):
            return None

        def mark_completed(self, job_id: str) -> None:
            return None

        def mark_failed(self, job_id: str) -> None:
            return None

    store = InvestigationStore()
    run = RunWorkerJob(
        runtime=SimpleNamespace(arun=AsyncMock(side_effect=RuntimeError("llm down"))),
        registry=SimpleNamespace(get=lambda _name: SimpleNamespace(
            schema_name="SocFinding",
            tools=[],
            skills=[],
            bus_recipients=[],
        )),
        bus=SimpleNamespace(
            send_message=lambda *a, **k: object(),
            receive_message=lambda *a, **k: None,
            record_agent_failure=lambda *a, **k: None,
        ),
        sandbox=SimpleNamespace(acreate=AsyncMock(return_value=SimpleNamespace(sandbox_id="sb-1")), adestroy=AsyncMock()),
        transport=SimpleNamespace(publish=AsyncMock()),
        queue=SimpleNamespace(),
        sanitizer=SimpleNamespace(sanitize=lambda x, source="": x),
        guardrails=SimpleNamespace(validate_schema=lambda r, s: r),
        job_store=JobStore(),
        use_tool_gateway=False,
        resolve_mcp_tools=lambda *a, **k: [],
        resolve_legacy_tools=lambda *a, **k: [],
        make_load_skill_tool=lambda *a, **k: None,
        investigation_store=store,
    )

    soc_job = WorkerJob(
        job_id="soc-evt-1-aaa",
        event_id="evt-1",
        persona="soc",
        correlation_id="inv-1",
    )
    result = await run.execute(soc_job, soc_job, "worker:soc:soc-evt-1-aaa", {})
    assert result.success is False
    assert completed == ["soc"]

    orch = WorkerOrchestrator(persona="network")
    orch._run_worker_job.investigation_store = store

    class _Container:
        def get_investigation_state_store(self):
            return store

    monkeypatch.setattr("interfaces.worker.orchestrator.get_container", lambda: _Container())

    async def fake_execute(job, budgeted, session_id, job_state):
        return RunResult(job_id=job.job_id, persona=job.persona, success=True)

    orch._run_worker_job.execute = fake_execute
    network_job = WorkerJob(
        job_id="network-evt-1-bbb",
        event_id="evt-1",
        persona="network",
        correlation_id="inv-1",
        depends_on_persona="soc",
    )
    gate = await orch.run_job(network_job)
    assert gate.success is True
    assert gate.error != "dependency_not_ready:soc"


@pytest.mark.unit
def test_enqueue_registers_pending_jobs(monkeypatch):
    pending: list[str] = []

    class JobStore:
        def upsert_pending(self, job_id, persona, **kwargs):
            pending.append(job_id)

        def upsert_running(self, *args, **kwargs):
            return None

        def mark_completed(self, job_id: str) -> None:
            return None

        def mark_failed(self, job_id: str) -> None:
            return None

        def pause_for_hitl(self, *args, **kwargs):
            return None

        def get(self, job_id: str):
            return None

        def mark_running(self, job_id: str):
            return None

        def list_pending_approvals(self):
            return []

        def list_by_investigation(self, tenant_id: str, investigation_id: str):
            return []

    class Queue:
        def enqueue(self, job):
            return job.get("job_id", "")

        async def aenqueue(self, job):
            return job.get("job_id", "")

    orch = WorkerOrchestrator(persona="soc")
    orch.job_store = JobStore()
    orch.queue = Queue()
    job_ids = orch.enqueue_from_routing_sync(
        "evt-pending",
        ["consultant"],
        correlation_id="inv-pending",
    )
    assert job_ids
    assert pending == job_ids
