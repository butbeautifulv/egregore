from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cys_core.application.use_cases.start_engagement import StartEngagement
from cys_core.domain.engagement.models import EngagementMode, EngagementStatus, PlanStrategy
from cys_core.domain.events.models import SecurityEvent
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
from tests.application.port_fakes import plan_investigation_port_kwargs


class _FakeDispatch:
    def __init__(self, enqueuer):
        self.enqueuer = enqueuer


@pytest.mark.unit
@pytest.mark.asyncio
async def test_plan_async_background_notifies_planning_then_enqueued() -> None:
    eng_store = MemoryEngagementStateStore()
    event = SecurityEvent(
        id="evt-1",
        type="engagement.start",
        source="api",
        severity="medium",
        payload={"goal": "investigate", "plan_strategy": "meta_llm"},
        correlation_id="inv-1",
    )
    runtime = AsyncMock()
    runtime.arun = AsyncMock(
        return_value={
            "personas": ["consultant"],
            "sub_goals": {"consultant": "investigate"},
            "rationale": "test plan",
        }
    )
    from cys_core.application.use_cases.meta_planner import MetaPlanner

    meta = MetaPlanner(
        runtime=runtime,
        engagement_store=eng_store,
        **plan_investigation_port_kwargs(
            resource_source=__import__("types").SimpleNamespace(
                list_worker_personas=lambda profile_id=None: ["consultant"]
            ),
        ),
    )
    enqueuer = MagicMock()
    enqueuer.enqueue_from_routing = AsyncMock(return_value=["job-1"])
    egress = MagicMock()
    start = StartEngagement(
        engagement_store=eng_store,
        dispatch=_FakeDispatch(enqueuer),
        egress=egress,
        meta_planner=meta,
    )
    eng_store.upsert(
        __import__(
            "cys_core.domain.engagement.models",
            fromlist=["Engagement"],
        ).Engagement(
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

    with patch("cys_core.application.resource_source.get_resource_source"):
        job_ids = await start.plan_async_background(event, event.payload)

    assert job_ids == ["job-1"]
    assert egress.publish_status.call_count >= 2
    planning_call = egress.publish_status.call_args_list[0]
    assert planning_call.args[1] == "planning"
    final_call = egress.publish_status.call_args_list[-1]
    assert final_call.args[1] == "enqueued"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_plan_async_background_publishes_error_on_failure() -> None:
    eng_store = MemoryEngagementStateStore()
    event = SecurityEvent(
        id="evt-2",
        type="engagement.start",
        source="api",
        severity="medium",
        payload={"goal": "investigate", "plan_strategy": "meta_llm"},
        correlation_id="inv-2",
    )
    runtime = AsyncMock()
    runtime.arun = AsyncMock(return_value={"personas": ["consultant"]})
    from cys_core.application.use_cases.meta_planner import MetaPlanner

    meta = MetaPlanner(
        runtime=runtime,
        engagement_store=eng_store,
        **plan_investigation_port_kwargs(
            resource_source=__import__("types").SimpleNamespace(
                list_worker_personas=lambda profile_id=None: ["consultant"]
            ),
        ),
    )
    enqueuer = MagicMock()
    enqueuer.enqueue_from_routing = AsyncMock(side_effect=RuntimeError("queue down"))
    egress = MagicMock()
    start = StartEngagement(
        engagement_store=eng_store,
        dispatch=_FakeDispatch(enqueuer),
        egress=egress,
        meta_planner=meta,
    )

    with patch("cys_core.application.resource_source.get_resource_source"):
        from cys_core.application.errors import PlanningFailedError

        with pytest.raises(PlanningFailedError):
            await start.plan_async_background(event, event.payload)

    error_call = egress.publish_status.call_args_list[-1]
    assert error_call.args[1] == "error"
