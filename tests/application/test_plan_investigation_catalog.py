from __future__ import annotations

from typing import Any

import pytest

from cys_core.application.use_cases.plan_investigation import PlanInvestigation
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
from tests.application.port_fakes import plan_investigation_port_kwargs


class _PlannerRuntime:
    async def arun(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"personas": ["soc", "unknown-persona"], "sub_goals": {}, "rationale": "test"}


@pytest.mark.unit
def test_planner_filters_to_catalog_personas():
    planner = PlanInvestigation(
        runtime=_PlannerRuntime(),
        engagement_store=MemoryEngagementStateStore(),
        profile_id="cybersec-soc",
        **plan_investigation_port_kwargs(),
    )
    available = planner._available_personas()
    assert "soc" in available
    assert "consultant" in available
