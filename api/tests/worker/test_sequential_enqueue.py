from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs
from cys_core.domain.workers.models import RunResult, WorkerJob
from interfaces.worker.orchestrator import WorkerOrchestrator
from tests.application.fakes.job_queue import FakeJobQueue, FakeJobStore
from tests.application.workers.factory import build_run_worker_job_for_tests


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dependency_not_ready_requeues_to_front(monkeypatch):
    from cys_core.infrastructure.queue import InMemoryJobQueue

    queue = InMemoryJobQueue()
    blocker = WorkerJob(
        job_id="soc-blocker",
        event_id="evt-1",
        persona="soc",
        correlation_id="inv-1",
    )
    queue.enqueue(blocker)

    class _Container:
        def get_job_queue(self, **kwargs):
            return queue

        def get_engagement_state_store(self):
            return EngagementStore()

        def get_job_store(self):
            return MagicMock()

        def get_run_worker_job(self, **kwargs):
            return MagicMock()

        def get_tool_chain_policy(self):
            return SimpleNamespace(clear=lambda *_a, **_k: None)

        def get_metrics_port(self):
            return MagicMock()

    class EngagementStore:
        def get(self, tenant_id: str, engagement_id: str):
            from cys_core.domain.engagement.models import Engagement, EngagementStatus

            return Engagement(
                id=engagement_id,
                tenant_id=tenant_id,
                goal="test",
                status=EngagementStatus.RUNNING,
                completed_personas=[],
            )

    monkeypatch.setattr("interfaces.worker.orchestrator.get_container", lambda: _Container())

    orch = WorkerOrchestrator(
        persona="network",
        runtime=MagicMock(),
        registry=MagicMock(),
        bus=MagicMock(),
    )
    orch.queue = queue
    network_job = WorkerJob(
        job_id="network-evt-1-bbb",
        event_id="evt-1",
        persona="network",
        correlation_id="inv-1",
        depends_on_persona="soc",
    )
    await orch.run_job(network_job)

    assert len(queue._queue) == 2
    assert queue._queue[0].job_id == "network-evt-1-bbb"
    assert queue._queue[1].job_id == "soc-blocker"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_upstream_unblocks_sequential_downstream(monkeypatch):
    from cys_core.infrastructure.queue import InMemoryJobQueue

    queue = InMemoryJobQueue()

    class _ContainerEarly:
        def get_job_queue(self, **kwargs):
            return queue

        def get_engagement_state_store(self):
            return MagicMock()

        def get_job_store(self):
            return MagicMock()

        def get_run_worker_job(self, **kwargs):
            return MagicMock()

        def get_tool_chain_policy(self):
            return SimpleNamespace(clear=lambda *_a, **_k: None)

        def get_metrics_port(self):
            return MagicMock()

    monkeypatch.setattr("interfaces.worker.orchestrator.get_container", lambda: _ContainerEarly())
    completed: list[str] = []
    failed: list[str] = []

    class EngagementStore:
        def mark_persona_done(self, tenant_id: str, engagement_id: str, persona: str) -> None:
            completed.append(persona)

        def mark_persona_failed(self, tenant_id: str, engagement_id: str, persona: str) -> None:
            failed.append(persona)

        def get(self, tenant_id: str, engagement_id: str):
            from cys_core.domain.engagement.models import Engagement, EngagementStatus

            return Engagement(
                id=engagement_id,
                tenant_id=tenant_id,
                goal="test",
                status=EngagementStatus.RUNNING,
                completed_personas=list(completed),
                failed_personas=list(failed),
            )

    class JobStore:
        def upsert_running(self, *args, **kwargs):
            return None

        def mark_completed(self, job_id: str) -> None:
            return None

        def mark_failed(self, job_id: str) -> None:
            return None

    store = EngagementStore()
    run = build_run_worker_job_for_tests(
        runtime=SimpleNamespace(arun=AsyncMock(side_effect=RuntimeError("llm down"))),
        engagement_store=store,
    )

    soc_job = WorkerJob(
        job_id="soc-evt-1-aaa",
        event_id="evt-1",
        persona="soc",
        correlation_id="inv-1",
    )
    result = await run.execute(soc_job, soc_job, "worker:soc:soc-evt-1-aaa", {})
    assert result.success is False
    assert failed == ["soc"]

    orch = WorkerOrchestrator(
        persona="network",
        runtime=MagicMock(),
        registry=MagicMock(),
        bus=MagicMock(),
    )
    orch.queue = InMemoryJobQueue()

    class _Container:
        def get_engagement_state_store(self):
            return store

        def get_tool_chain_policy(self):
            return SimpleNamespace(clear=lambda *_a, **_k: None)

        def get_job_queue(self, **kwargs):
            return orch.queue

        def get_metrics_port(self):
            return MagicMock()

        def get_agent_catalog(self):
            return MagicMock(get_agent=MagicMock(return_value=None))

        @property
        def settings(self):
            return SimpleNamespace(
                resolve_worker_job_timeout=lambda **kwargs: 300.0,
                job_cost_per_1k_tokens_usd=0.01,
            )

        def get_profile_policy_port(self):
            return MagicMock(get_cost_per_1k_tokens=MagicMock(return_value=0.01))

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
def test_enqueue_registers_pending_jobs():
    store = FakeJobStore()
    queue = FakeJobQueue()
    service = EnqueueWorkerJobs(queue=queue, job_store=store)
    job_ids = service.enqueue_from_routing_sync(
        "evt-pending",
        ["consultant"],
        correlation_id="inv-pending",
    )
    assert job_ids
    assert store.pending == job_ids
