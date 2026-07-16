from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus, PlanStrategy
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore


@pytest.mark.unit
def test_mark_persona_done_closes_consultant_only_plan() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="evt-ad",
            tenant_id="default",
            goal="advisory",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["consultant"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
        )
    )
    store.mark_persona_done("default", "evt-ad", "consultant")
    state = store.get("default", "evt-ad")
    assert state is not None
    assert state.status == EngagementStatus.CLOSED
    assert state.completed_personas == ["consultant"]


@pytest.mark.unit
def test_run_worker_job_publishes_egress_after_terminal() -> None:
    from tests.application.workers.factory import build_run_worker_job_for_tests

    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="evt-1",
            tenant_id="default",
            goal="investigate",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["consultant"],
            plan_strategy=PlanStrategy.META_LLM,
        )
    )
    egress = MagicMock()
    job = WorkerJob(
        job_id="consultant-evt-1-abc",
        event_id="evt-1",
        persona="consultant",
        correlation_id="evt-1",
    )
    runner = build_run_worker_job_for_tests(
        engagement_store=store,
        engagement_egress=egress,
    )
    runner._mark_persona_completed(job)
    egress.publish_status.assert_called_once()
    call_args = egress.publish_status.call_args
    assert call_args.args[0] == "evt-1"
    assert call_args.args[1] == "job_update"
    assert call_args.args[2]["completed_personas"] == ["consultant"]
