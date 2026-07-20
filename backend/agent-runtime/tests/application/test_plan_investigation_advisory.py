from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.errors import PlanningFailedError
from cys_core.application.use_cases.plan_investigation import PlanInvestigation
from cys_core.domain.engagement.models import Engagement, EngagementStatus
from cys_core.domain.events.models import SecurityEvent
from tests.application.port_fakes import fake_resource_source, plan_investigation_port_kwargs


@pytest.mark.unit
@pytest.mark.asyncio
async def test_plan_investigation_advisory_goal_uses_llm() -> None:
    runtime = MagicMock()
    runtime.arun = AsyncMock(
        return_value={
            "personas": ["consultant"],
            "sub_goals": {"consultant": "Как мне избежать вирусов?"},
            "rationale": "general_ib_advisory",
        }
    )
    store = MagicMock()
    store.get.return_value = Engagement(
        id="inv-virus",
        tenant_id="default",
        goal="Как мне избежать вирусов?",
        status=EngagementStatus.PLANNING,
        planner_status="planning",
    )
    planner = PlanInvestigation(runtime=runtime, engagement_store=store, **plan_investigation_port_kwargs())
    event = SecurityEvent(
        id="evt-virus",
        type="engagement.start",
        severity="low",
        source="test",
        payload={"goal": "Как мне избежать вирусов?", "plan_strategy": "meta_llm"},
        correlation_id="inv-virus",
        tenant_id="default",
    )
    plan = await planner.execute(event)
    assert plan.personas == ["consultant"]
    assert plan.rationale == "general_ib_advisory"
    runtime.arun.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_plan_investigation_unparseable_llm_fails_fast() -> None:
    runtime = MagicMock()
    runtime.arun = AsyncMock(return_value={"raw_response": "not-json"})
    store = MagicMock()
    store.get.return_value = Engagement(
        id="inv-fb",
        tenant_id="default",
        goal="Investigate lateral movement on host X",
        status=EngagementStatus.PLANNING,
        planner_status="planning",
    )
    kwargs = plan_investigation_port_kwargs(
        resource_source=fake_resource_source(personas=["cloud", "coding", "compliance", "consultant", "soc"])
    )
    planner = PlanInvestigation(runtime=runtime, engagement_store=store, **kwargs)
    event = SecurityEvent(
        id="evt-fb",
        type="engagement.start",
        severity="high",
        source="test",
        payload={"goal": "Investigate lateral movement on host X", "plan_strategy": "meta_llm"},
        correlation_id="inv-fb",
        tenant_id="default",
    )
    with pytest.raises(PlanningFailedError):
        await planner.execute(event)
    store.update_planner_state.assert_called()
    call_kwargs = store.update_planner_state.call_args.kwargs
    assert call_kwargs["planner_status"] == "error"
    assert call_kwargs["planner_error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_plan_investigation_structured_output_ok() -> None:
    runtime = MagicMock()
    runtime.arun = AsyncMock(
        return_value={
            "personas": ["network", "consultant"],
            "sub_goals": {
                "network": "Assess LAN segmentation",
                "consultant": "Summarize recommendations",
            },
            "rationale": "network_hardening_advisory",
            "plan_status": "ready",
        }
    )
    store = MagicMock()
    store.get.return_value = Engagement(
        id="inv-net",
        tenant_id="default",
        goal="Как сделать надёжной локальную сетку?",
        status=EngagementStatus.PLANNING,
        planner_status="planning",
    )
    # FakePersonaRanking.rank() already returns personas unchanged by default.
    kwargs = plan_investigation_port_kwargs(
        resource_source=fake_resource_source(personas=["network", "consultant", "soc"])
    )
    planner = PlanInvestigation(runtime=runtime, engagement_store=store, **kwargs)
    event = SecurityEvent(
        id="evt-net",
        type="engagement.start",
        severity="low",
        source="test",
        payload={"goal": "Как сделать надёжной локальную сетку?", "plan_strategy": "meta_llm"},
        correlation_id="inv-net",
        tenant_id="default",
    )
    plan = await planner.execute(event)
    assert plan.personas == ["network", "consultant"]
    assert plan.rationale == "network_hardening_advisory"
    assert "fallback" not in plan.rationale


@pytest.mark.unit
@pytest.mark.asyncio
async def test_plan_investigation_unwraps_guardrails_response_json() -> None:
    runtime = MagicMock()
    runtime.arun = AsyncMock(
        return_value={
            "response": (
                '{"personas": ["consultant"], "sub_goals": ["Supply chain basics"], '
                '"rationale": "advisory via response wrapper"}'
            ),
        }
    )
    store = MagicMock()
    store.get.return_value = Engagement(
        id="inv-wrap",
        tenant_id="default",
        goal="Advisory: supply chain security basics",
        status=EngagementStatus.PLANNING,
        planner_status="planning",
    )
    planner = PlanInvestigation(runtime=runtime, engagement_store=store, **plan_investigation_port_kwargs())
    event = SecurityEvent(
        id="evt-wrap",
        type="engagement.start",
        severity="low",
        source="test",
        payload={"goal": "Advisory: supply chain security basics", "plan_strategy": "meta_llm"},
        correlation_id="inv-wrap",
        tenant_id="default",
    )
    plan = await planner.execute(event)
    assert plan.personas == ["consultant"]
    assert plan.rationale == "advisory via response wrapper"
    assert plan.sub_goals["consultant"] == "Supply chain basics"
