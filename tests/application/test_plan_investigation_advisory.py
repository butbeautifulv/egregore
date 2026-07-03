from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.plan_investigation import PlanInvestigation
from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.memory.models import InvestigationState


@pytest.mark.unit
@pytest.mark.asyncio
async def test_plan_investigation_advisory_skips_llm() -> None:
    runtime = AsyncMock()
    store = MagicMock()
    store.get.return_value = InvestigationState(
        investigation_id="inv-1",
        tenant_id="default",
        goal="Как защитить Active Directory?",
        status="in_progress",
        planner_status="planning",
    )
    planner = PlanInvestigation(runtime=runtime, investigation_store=store)
    event = SecurityEvent(
        id="evt-1",
        type="manual.investigation",
        severity="low",
        source="test",
        payload={"goal": "Как защитить Active Directory?"},
        correlation_id="inv-1",
        tenant_id="default",
    )
    plan = await planner.execute(event)
    assert plan.personas == ["consultant"]
    assert plan.rationale == "advisory_fast_path_consultant_only"
    runtime.arun.assert_not_called()
