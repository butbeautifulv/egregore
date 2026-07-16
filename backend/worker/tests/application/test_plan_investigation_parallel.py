from __future__ import annotations

from typing import Any

import pytest

from cys_core.application.planning.catalog_planner_strategy import CatalogPlannerStrategy
from cys_core.application.use_cases.plan_investigation import PlanInvestigation
from cys_core.domain.engagement.models import EngagementPlan, ExecutionMode
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
from tests.application.port_fakes import plan_investigation_port_kwargs


class _PlannerRuntime:
    async def arun(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"personas": ["soc"], "sub_goals": {}, "rationale": "test"}


def _planner() -> PlanInvestigation:
    return PlanInvestigation(
        runtime=_PlannerRuntime(),
        engagement_store=MemoryEngagementStateStore(),
        **plan_investigation_port_kwargs(),
    )


def _strategy() -> CatalogPlannerStrategy:
    return CatalogPlannerStrategy(
        runtime=_PlannerRuntime(),
        engagement_store=MemoryEngagementStateStore(),
        **plan_investigation_port_kwargs(),
    )


@pytest.mark.unit
def test_pipeline_staged_only_for_staged_mode() -> None:
    parallel_plan = EngagementPlan(
        personas=["soc", "intel"],
        execution_mode=ExecutionMode.PARALLEL,
    )
    staged_plan = EngagementPlan(
        personas=["soc", "intel"],
        execution_mode=ExecutionMode.STAGED,
    )
    assert parallel_plan.is_pipeline_staged() is False
    assert staged_plan.is_pipeline_staged() is True
    assert EngagementPlan(personas=["consultant"]).is_pipeline_staged() is False


@pytest.mark.unit
def test_finalize_plan_sets_synthesis_for_multi_persona() -> None:
    strategy = _strategy()
    plan = EngagementPlan(personas=["soc", "intel", "hunter"])
    finalized = strategy._finalize_plan(plan, synthesis_default="consultant")
    assert finalized.synthesis_persona == "consultant"
    assert finalized.execution_mode == ExecutionMode.PARALLEL

    single = strategy._finalize_plan(EngagementPlan(personas=["consultant"]), synthesis_default="consultant")
    assert single.synthesis_persona is None


@pytest.mark.unit
def test_to_worker_jobs_payload_includes_execution_fields() -> None:
    planner = _planner()
    payload = planner.to_worker_jobs_payload(
        EngagementPlan(
            personas=["soc", "intel"],
            execution_mode=ExecutionMode.PARALLEL,
            synthesis_persona="consultant",
        )
    )
    assert payload["execution_mode"] == "parallel"
    assert payload["synthesis_persona"] == "consultant"
    assert payload["phase"] == "specialist"
