from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.enqueue_synthesis_job import EnqueueSynthesisJob
from cys_core.application.use_cases.plan_investigation import PlanInvestigation
from cys_core.application.workers.job_finalizer import WorkerJobFinalizer
from cys_core.domain.engagement.models import (
    Engagement,
    EngagementMode,
    EngagementPlan,
    EngagementStatus,
    ExecutionMode,
    PlanStrategy,
    SynthesisStatus,
)
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
from cys_core.infrastructure.queue import InMemoryJobQueue


def _planner() -> PlanInvestigation:
    return PlanInvestigation(
        runtime=MagicMock(),
        engagement_store=MagicMock(),
        resource_source=MagicMock(),
        persona_ranking=MagicMock(),
        agent_catalog=MagicMock(),
    )


@pytest.mark.unit
def test_finalize_plan_soc_only_sets_consultant_synthesis() -> None:
    plan = _planner()._finalize_plan(EngagementPlan(personas=["soc"]))
    assert plan.synthesis_persona == "consultant"
    assert plan.execution_mode == ExecutionMode.PARALLEL


@pytest.mark.unit
def test_finalize_plan_consultant_only_skips_synthesis() -> None:
    plan = _planner()._finalize_plan(EngagementPlan(personas=["consultant"]))
    assert plan.synthesis_persona is None
    assert plan.execution_mode == ExecutionMode.PARALLEL


@pytest.mark.unit
def test_ensure_soc_intel_for_incident_adds_intel_staged() -> None:
    planner = _planner()
    planner.resource_source.list_worker_personas.return_value = ["soc", "intel", "consultant"]
    plan = EngagementPlan(personas=["soc"], sub_goals={"soc": "Investigate INC-893812"})
    updated = planner._ensure_soc_intel_for_incident(plan, "Investigate INC-893812")
    assert updated.personas == ["soc", "intel"]
    assert updated.execution_mode == ExecutionMode.STAGED
    assert updated.sub_goals["intel"] == "Investigate INC-893812"


@pytest.mark.unit
def test_apply_planner_result_soc_only_pending_synthesis() -> None:
    engagement = Engagement(id="eng-soc", tenant_id="default", goal="triage INC-1")
    engagement.apply_planner_result(
        ["soc"],
        status="ok",
        execution_mode=ExecutionMode.PARALLEL,
        synthesis_persona="consultant",
    )
    assert engagement.synthesis_persona == "consultant"
    assert engagement.synthesis_status == SynthesisStatus.PENDING


@pytest.mark.unit
def test_apply_planner_result_consultant_only_skips_synthesis() -> None:
    engagement = Engagement(id="eng-adv", tenant_id="default", goal="advisory")
    engagement.apply_planner_result(
        ["consultant"],
        status="ok",
        execution_mode=ExecutionMode.PARALLEL,
        synthesis_persona=None,
    )
    assert engagement.synthesis_status == SynthesisStatus.SKIPPED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_synthesis_after_soc_only_success() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="inv-soc-synth",
            tenant_id="default",
            goal="Investigate INC-893775",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["soc"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
            synthesis_persona="consultant",
            synthesis_status=SynthesisStatus.PENDING,
            execution_mode=ExecutionMode.PARALLEL,
            job_ids=["soc-inv-soc-synth-aaa"],
            completed_personas=["soc"],
            findings_summary=[{"persona": "soc", "finding": {"summary": "phishing alert"}}],
        )
    )
    queue = InMemoryJobQueue()
    synth = EnqueueSynthesisJob(engagement_store=store, queue=queue)
    soc_job = WorkerJob(
        job_id="soc-inv-soc-synth-aaa",
        event_id="evt-soc-synth",
        persona="soc",
        correlation_id="inv-soc-synth",
        payload={"goal": "Investigate INC-893775", "phase": "specialist"},
    )

    job_id = await synth.execute(soc_job)

    assert job_id == "consultant-inv-soc-synth-synth"
    assert len(queue._queue) == 1
    assert queue._queue[0].persona == "consultant"
    assert queue._queue[0].payload.get("phase") == "synthesis"
    engagement = store.get("default", "inv-soc-synth")
    assert engagement is not None
    assert engagement.synthesis_status == SynthesisStatus.RUNNING


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_synthesis_after_soc_failed() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="inv-soc-fail",
            tenant_id="default",
            goal="Investigate INC-893775",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["soc"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
            synthesis_persona="consultant",
            synthesis_status=SynthesisStatus.PENDING,
            execution_mode=ExecutionMode.PARALLEL,
            job_ids=["soc-inv-soc-fail-aaa"],
            failed_personas=["soc"],
        )
    )
    queue = InMemoryJobQueue()
    synth = EnqueueSynthesisJob(engagement_store=store, queue=queue)
    finalizer = WorkerJobFinalizer(
        job_store=MagicMock(mark_failed=MagicMock()),
        queue=queue,
        bus=MagicMock(record_agent_failure=MagicMock()),
        agent_catalog=MagicMock(get_agent=MagicMock(return_value=None)),
        engagement_store=store,
        enqueue_synthesis_job=synth,
    )
    soc_job = WorkerJob(
        job_id="soc-inv-soc-fail-aaa",
        event_id="evt-soc-fail",
        persona="soc",
        correlation_id="inv-soc-fail",
        payload={"goal": "Investigate INC-893775", "phase": "specialist"},
    )
    soc_job.transition_to(WorkerJobStatus.RUNNING)

    await finalizer.mark_runtime_failure(soc_job, "ungrounded_finding")

    assert len(queue._queue) == 1
    assert queue._queue[0].persona == "consultant"
    outcomes = queue._queue[0].payload.get("specialist_outcomes") or []
    assert outcomes[0]["persona"] == "soc"
    assert outcomes[0]["status"] == "failed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parallel_specialists_enqueue_single_synthesis() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="inv-parallel-synth",
            tenant_id="default",
            goal="investigate ip",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["soc", "intel"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
            synthesis_persona="consultant",
            synthesis_status=SynthesisStatus.PENDING,
            execution_mode=ExecutionMode.PARALLEL,
            job_ids=["soc-inv-parallel-synth-aaa", "intel-inv-parallel-synth-bbb"],
            completed_personas=["soc", "intel"],
        )
    )
    queue = InMemoryJobQueue()
    synth = EnqueueSynthesisJob(engagement_store=store, queue=queue)
    intel_job = WorkerJob(
        job_id="intel-inv-parallel-synth-bbb",
        event_id="evt-parallel-synth",
        persona="intel",
        correlation_id="inv-parallel-synth",
        payload={"execution_mode": "parallel", "phase": "specialist"},
    )

    first = await synth.execute(intel_job)
    second = await synth.execute(intel_job)

    assert first == "consultant-inv-parallel-synth-synth"
    assert second is None
    assert len(queue._queue) == 1
    assert queue._queue[0].persona == "consultant"
