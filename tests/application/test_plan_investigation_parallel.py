from __future__ import annotations

import pytest

from cys_core.application.use_cases.plan_investigation import PlanInvestigation
from cys_core.application.use_cases.start_engagement import _pipeline_staged
from cys_core.domain.engagement.models import EngagementPlan, ExecutionMode
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore


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
    assert _pipeline_staged(parallel_plan) is False
    assert _pipeline_staged(staged_plan) is True
    assert _pipeline_staged(EngagementPlan(personas=["consultant"])) is False


@pytest.mark.unit
def test_finalize_plan_sets_synthesis_for_multi_persona() -> None:
    store = MemoryEngagementStateStore()
    planner = PlanInvestigation(
        runtime=object(),  # type: ignore[arg-type]
        engagement_store=store,
        resource_source=object(),  # type: ignore[arg-type]
        persona_ranking=object(),  # type: ignore[arg-type]
        agent_catalog=object(),  # type: ignore[arg-type]
    )
    plan = EngagementPlan(personas=["soc", "intel", "hunter"])
    finalized = planner._finalize_plan(plan)
    assert finalized.synthesis_persona == "consultant"
    assert finalized.execution_mode == ExecutionMode.PARALLEL

    single = planner._finalize_plan(EngagementPlan(personas=["consultant"]))
    assert single.synthesis_persona is None


@pytest.mark.unit
def test_to_worker_jobs_payload_includes_execution_fields() -> None:
    store = MemoryEngagementStateStore()
    planner = PlanInvestigation(
        runtime=object(),  # type: ignore[arg-type]
        engagement_store=store,
        resource_source=object(),  # type: ignore[arg-type]
        persona_ranking=object(),  # type: ignore[arg-type]
        agent_catalog=object(),  # type: ignore[arg-type]
    )
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
