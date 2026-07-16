from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.enqueue_synthesis_job import EnqueueSynthesisJob
from cys_core.domain.engagement.models import (
    Engagement,
    EngagementMode,
    EngagementStatus,
    ExecutionMode,
    PlanStrategy,
    SynthesisStatus,
)
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
from cys_core.infrastructure.queue import InMemoryJobQueue


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesis_enqueued_when_all_specialists_terminal() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="eng-synth",
            tenant_id="default",
            goal="investigate traffic",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["soc", "intel"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
            execution_mode=ExecutionMode.PARALLEL,
            synthesis_persona="consultant",
            synthesis_status=SynthesisStatus.PENDING,
            job_ids=["soc-eng-synth-aaa", "intel-eng-synth-bbb"],
            completed_personas=["soc"],
            failed_personas=["intel"],
            findings_summary=[{"persona": "soc", "finding": {"summary": "alert"}}],
        )
    )
    queue = InMemoryJobQueue()
    egress = MagicMock()
    use_case = EnqueueSynthesisJob(engagement_store=store, queue=queue, engagement_egress=egress)
    intel_job = WorkerJob(
        job_id="intel-eng-synth-bbb",
        event_id="evt-synth",
        persona="intel",
        correlation_id="eng-synth",
        payload={
            "goal": "investigate traffic",
            "execution_mode": "parallel",
            "phase": "specialist",
        },
    )

    job_id = await use_case.execute(intel_job)

    assert job_id == "consultant-eng-synth-synth"
    assert len(queue._queue) == 1
    assert queue._queue[0].persona == "consultant"
    assert queue._queue[0].payload.get("phase") == "synthesis"
    engagement = store.get("default", "eng-synth")
    assert engagement is not None
    assert engagement.synthesis_status == SynthesisStatus.RUNNING
    egress.publish_status.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesis_not_enqueued_until_all_specialists_done() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="eng-partial",
            tenant_id="default",
            goal="investigate",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["soc", "intel"],
            synthesis_persona="consultant",
            synthesis_status=SynthesisStatus.PENDING,
            job_ids=["soc-eng-partial-aaa", "intel-eng-partial-bbb"],
            completed_personas=["soc"],
        )
    )
    queue = InMemoryJobQueue()
    use_case = EnqueueSynthesisJob(engagement_store=store, queue=queue)
    soc_job = WorkerJob(
        job_id="soc-eng-partial-aaa",
        event_id="evt-partial",
        persona="soc",
        correlation_id="eng-partial",
        payload={"phase": "specialist", "execution_mode": "parallel"},
    )

    job_id = await use_case.execute(soc_job)

    assert job_id is None
    assert len(queue._queue) == 0


@pytest.mark.unit
def test_single_persona_closes_without_synthesis() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="eng-one",
            tenant_id="default",
            goal="advisory",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["consultant"],
            synthesis_status=SynthesisStatus.SKIPPED,
        )
    )
    store.mark_persona_done("default", "eng-one", "consultant")
    engagement = store.get("default", "eng-one")
    assert engagement is not None
    assert engagement.status == EngagementStatus.CLOSED


@pytest.mark.unit
def test_multi_persona_waits_for_synthesis_before_close() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="eng-wait",
            tenant_id="default",
            goal="incident",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["soc", "intel"],
            synthesis_persona="consultant",
            synthesis_status=SynthesisStatus.PENDING,
        )
    )
    store.mark_persona_done("default", "eng-wait", "soc")
    store.mark_persona_done("default", "eng-wait", "intel")
    engagement = store.get("default", "eng-wait")
    assert engagement is not None
    assert engagement.status == EngagementStatus.RUNNING

    store.set_final_report("default", "eng-wait", {"summary": "final", "recommendations": ["a", "b", "c"]})
    engagement = store.get("default", "eng-wait")
    assert engagement is not None
    assert engagement.status == EngagementStatus.CLOSED
    assert engagement.final_report is not None
    assert engagement.synthesis_status == SynthesisStatus.DONE
