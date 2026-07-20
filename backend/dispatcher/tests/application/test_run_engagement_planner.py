from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.errors import PlanningFailedError
from cys_core.application.use_cases.meta_planner import MetaPlanner
from cys_core.application.use_cases.run_engagement_planner import EngagementPlannerRunner
from cys_core.domain.engagement.models import Engagement as EngagementModel
from cys_core.domain.engagement.models import EngagementMode, EngagementStatus, PlanStrategy
from cys_core.domain.engagement.planner_job import ENGAGEMENT_PLAN_WORK_KIND, ENGAGEMENT_PLANNER_PERSONA
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
from tests.application.port_fakes import plan_investigation_port_kwargs


class _FakeDispatch:
    def __init__(self, enqueuer):
        self.enqueuer = enqueuer


def _planner_job(investigation_id: str) -> WorkerJob:
    return WorkerJob(
        job_id=f"planner-{investigation_id}",
        event_id=investigation_id,
        persona=ENGAGEMENT_PLANNER_PERSONA,
        correlation_id=investigation_id,
        tenant_id="default",
        payload={"goal": "investigate", "plan_strategy": "meta_llm", "work_kind": ENGAGEMENT_PLAN_WORK_KIND},
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engagement_planner_runner_notifies_enqueued_on_success() -> None:
    eng_store = MemoryEngagementStateStore()
    eng_store.upsert(
        EngagementModel(
            id="inv-1",
            tenant_id="default",
            profile_id="cybersec-soc",
            domain_id="",
            goal="investigate",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.PLANNING,
            correlation_id="inv-1",
            plan_strategy=PlanStrategy.META_LLM,
        )
    )
    runtime = AsyncMock()
    runtime.arun = AsyncMock(
        return_value={
            "personas": ["consultant"],
            "sub_goals": {"consultant": "investigate"},
            "rationale": "test plan",
        }
    )
    meta = MetaPlanner(
        runtime=runtime,
        engagement_store=eng_store,
        **plan_investigation_port_kwargs(
            resource_source=SimpleNamespace(list_worker_personas=lambda profile_id=None: ["consultant"]),
        ),
    )
    enqueuer = MagicMock()
    enqueuer.enqueue_from_routing = AsyncMock(return_value=["job-1"])
    egress = MagicMock()
    runner = EngagementPlannerRunner(
        meta_planner=meta,
        dispatch=_FakeDispatch(enqueuer),
        engagement_store=eng_store,
        engagement_egress=egress,
    )

    result = await runner.execute(_planner_job("inv-1"), "inv-1")

    assert result["job_ids"] == ["job-1"]
    final_call = egress.publish_status.call_args_list[-1]
    assert final_call.args[1] == "enqueued"

    stored = eng_store.get("default", "inv-1")
    assert stored is not None
    assert stored.status == EngagementStatus.ENQUEUED
    assert stored.job_ids == ["job-1"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engagement_planner_runner_publishes_error_on_enqueue_failure() -> None:
    eng_store = MemoryEngagementStateStore()
    runtime = AsyncMock()
    runtime.arun = AsyncMock(return_value={"personas": ["consultant"]})
    meta = MetaPlanner(
        runtime=runtime,
        engagement_store=eng_store,
        **plan_investigation_port_kwargs(
            resource_source=SimpleNamespace(list_worker_personas=lambda profile_id=None: ["consultant"]),
        ),
    )
    enqueuer = MagicMock()
    enqueuer.enqueue_from_routing = AsyncMock(side_effect=RuntimeError("queue down"))
    egress = MagicMock()
    runner = EngagementPlannerRunner(
        meta_planner=meta,
        dispatch=_FakeDispatch(enqueuer),
        engagement_store=eng_store,
        engagement_egress=egress,
    )

    with pytest.raises(PlanningFailedError):
        await runner.execute(_planner_job("inv-2"), "inv-2")

    error_call = egress.publish_status.call_args_list[-1]
    assert error_call.args[1] == "error"
