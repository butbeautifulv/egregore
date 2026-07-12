from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.start_work_order import StartWorkOrder
from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus, PlanStrategy
from cys_core.domain.events.models import RoutingDecision
from cys_core.domain.work_order.models import WorkOrderRequest
from cys_core.domain.workspace.models import Workspace


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_work_order_persists_initial_turn() -> None:
    memory_writer = MagicMock()
    memory_writer.append_conversation_turn.return_value = MagicMock(id="mem-1")
    engagement = Engagement(
        id="eng-test123456",
        goal="Investigate phishing",
        mode=EngagementMode.ASYNC,
        status=EngagementStatus.CREATED,
        plan_strategy=PlanStrategy.META_LLM,
    )
    start_engagement = MagicMock()
    start_engagement.execute = AsyncMock(
        return_value=(
            engagement,
            RoutingDecision(
                event_id=engagement.id,
                personas=[],
                playbook_id="engagement-meta-llm",
                notify_control=True,
                reason="async_planner_pending",
            ),
            [],
        )
    )
    work_order_store = MagicMock()
    use_case = StartWorkOrder(
        work_order_store=work_order_store,
        start_engagement=start_engagement,
        memory_writer=memory_writer,
        memory_reader=MagicMock(),
        engagement_store=MagicMock(),
    )
    request = WorkOrderRequest(goal="Investigate phishing", intent_mode="plan")
    await use_case.execute(request)
    memory_writer.append_conversation_turn.assert_called_once()
    call_kwargs = memory_writer.append_conversation_turn.call_args.kwargs
    assert call_kwargs["follow_up_id"] == "wo-eng-test123456"
    assert call_kwargs["mode"] == "plan"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_work_order_resolves_default_workspace() -> None:
    engagement = Engagement(
        id="eng-test123456",
        tenant_id="acme",
        goal="Investigate phishing",
        mode=EngagementMode.ASYNC,
        status=EngagementStatus.CREATED,
        plan_strategy=PlanStrategy.META_LLM,
    )
    start_engagement = MagicMock()
    start_engagement.execute = AsyncMock(
        return_value=(
            engagement,
            RoutingDecision(
                event_id=engagement.id,
                personas=[],
                playbook_id="engagement-meta-llm",
                notify_control=True,
                reason="async_planner_pending",
            ),
            [],
        )
    )
    workspace_store = MagicMock()
    workspace_store.get.return_value = None
    workspace_store.create.return_value = Workspace(
        id="acme-default",
        organization_id="acme",
        name="Default",
        created_by="system",
    )
    use_case = StartWorkOrder(
        work_order_store=MagicMock(),
        start_engagement=start_engagement,
        workspace_store=workspace_store,
    )

    await use_case.execute(WorkOrderRequest(goal="Investigate phishing", tenant_id="acme"))

    engagement_request = start_engagement.execute.call_args.args[0]
    assert engagement_request.workspace_id == "acme-default"
