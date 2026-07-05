from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.plan_investigation import PlanInvestigation
from tests.application.port_fakes import plan_investigation_port_kwargs


class _Runtime:
    async def arun(self, *args, **kwargs):
        return {"personas": ["soc", "unknown-persona"], "sub_goals": {}, "rationale": "test"}


class _FakeStore:
    def get(self, tenant_id, engagement_id):
        return None

    def upsert(self, engagement):
        return None

    def update_planner_state(self, *args, **kwargs):
        return None


@pytest.mark.unit
def test_planner_filters_to_catalog_personas():
    planner = PlanInvestigation(
        runtime=_Runtime(),
        engagement_store=_FakeStore(),
        profile_id="cybersec-soc",
        **plan_investigation_port_kwargs(
            resource_source=MagicMock(list_worker_personas=lambda profile_id=None: ["soc", "consultant"]),
        ),
    )
    available = planner._available_personas()
    assert "soc" in available
    assert "consultant" in available


@pytest.mark.unit
def test_planner_ranks_personas_via_port():
    ranking = MagicMock()
    ranking.rank.return_value = ["network", "soc"]
    planner = PlanInvestigation(
        runtime=_Runtime(),
        engagement_store=_FakeStore(),
        **plan_investigation_port_kwargs(persona_ranking=ranking),
    )
    ranked = planner.persona_ranking.rank(["soc", "network"], profile_id="cybersec-soc")
    assert ranked == ["network", "soc"]
    ranking.rank.assert_called_once()
