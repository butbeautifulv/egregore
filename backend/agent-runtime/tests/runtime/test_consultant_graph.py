from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog
from langchain_core.messages import AIMessage, HumanMessage

from cys_core.application.planning.planner_strategy import (
    DeterministicAdvisoryPlannerStrategy,
    PlannerContext,
    PlannerRouter,
)
from cys_core.application.planning.signals import PlannerSignalDetector
from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    record_tool_success,
)
from cys_core.domain.catalog.models import PlannerPack, ProfilePack
from cys_core.domain.engagement.models import Engagement, EngagementPlan
from cys_core.domain.events.models import SecurityEvent
from cys_core.runtime.consultant_graph import build_consultant_graph


def _mock_runtime() -> MagicMock:
    runtime = MagicMock()
    runtime.model_connector.create_model.return_value = MagicMock()
    runtime._build_middleware.return_value = []
    runtime._build_synthesize_middleware.return_value = []
    return runtime


@pytest.mark.unit
def test_build_consultant_graph_compiles() -> None:
    defn = SimpleNamespace(
        name="consultant",
        system_prompt="You are a consultant.",
        schema_name="ConsultantFinding",
    )
    graph = build_consultant_graph(
        _mock_runtime(),
        defn,
        model=MagicMock(),
        tools=[],
        checkpointer=None,
        store=None,
        session_id="sess-1",
        tenant_id="default",
        investigation_id="eng-1",
        profile_id="cybersec-soc",
        goal="test goal",
        job_id="job-1",
    )
    assert graph is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_consultant_graph_routes_to_synthesize_when_ladder_complete() -> None:
    job_id = "job-graph-route"
    clear_tool_execution_count(job_id)
    record_tool_success(job_id, "load_skill")
    structlog.contextvars.bind_contextvars(job_id=job_id)

    defn = SimpleNamespace(
        name="consultant",
        system_prompt="You are a consultant.",
        schema_name="ConsultantFinding",
    )

    research_result = {"messages": [HumanMessage(content="goal"), AIMessage(content="researched")]}
    synthesize_result = {
        "messages": [HumanMessage(content="goal"), AIMessage(content='{"topic":"t"}')],
        "structured_response": {"topic": "security", "summary": "ok", "recommendations": ["a", "b"], "confidence": 0.8},
    }

    with patch("cys_core.runtime.consultant_graph.create_agent") as create_agent:
        research_agent = MagicMock()
        research_agent.ainvoke = AsyncMock(return_value=research_result)
        synthesize_agent = MagicMock()
        synthesize_agent.ainvoke = AsyncMock(return_value=synthesize_result)
        create_agent.side_effect = [research_agent, synthesize_agent]

        graph = build_consultant_graph(
            _mock_runtime(),
            defn,
            model=MagicMock(),
            tools=[MagicMock()],
            checkpointer=None,
            store=None,
            session_id=job_id,
            tenant_id="default",
            investigation_id="eng-route",
            profile_id="cybersec-soc",
            goal="Как обеспечить безопасность мультиагентной системы?",
            job_id=job_id,
        )

        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="Как обеспечить безопасность мультиагентной системы?")],
                "research_steps": 0,
                "job_id": job_id,
            }
        )

    assert synthesize_agent.ainvoke.await_count == 1
    assert research_agent.ainvoke.await_count == 1
    assert "structured_response" in result or result.get("messages")
    clear_tool_execution_count(job_id)
    structlog.contextvars.clear_contextvars()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_consultant_graph_synthesizes_after_research_recursion_error() -> None:
    job_id = "job-graph-recursion"
    clear_tool_execution_count(job_id)
    structlog.contextvars.bind_contextvars(job_id=job_id)

    defn = SimpleNamespace(
        name="consultant",
        system_prompt="You are a consultant.",
        schema_name="ConsultantFinding",
    )

    synthesize_result = {
        "messages": [HumanMessage(content="goal"), AIMessage(content='{"topic":"t"}')],
        "structured_response": {
            "topic": "security",
            "summary": "ok",
            "recommendations": ["a", "b"],
            "confidence": 0.8,
        },
    }

    with patch("cys_core.runtime.consultant_graph.create_agent") as create_agent:
        research_agent = MagicMock()
        research_agent.ainvoke = AsyncMock(side_effect=RuntimeError("Recursion limit of 3 reached"))
        synthesize_agent = MagicMock()
        synthesize_agent.ainvoke = AsyncMock(return_value=synthesize_result)
        create_agent.side_effect = [research_agent, synthesize_agent]

        graph = build_consultant_graph(
            _mock_runtime(),
            defn,
            model=MagicMock(),
            tools=[MagicMock()],
            checkpointer=None,
            store=None,
            session_id=job_id,
            tenant_id="default",
            investigation_id="eng-recursion",
            profile_id="cybersec-soc",
            goal="How to secure multi-agent systems?",
            job_id=job_id,
        )

        await graph.ainvoke(
            {
                "messages": [HumanMessage(content="How to secure multi-agent systems?")],
                "research_steps": 0,
                "job_id": job_id,
            }
        )

    assert synthesize_agent.ainvoke.await_count == 1
    clear_tool_execution_count(job_id)
    structlog.contextvars.clear_contextvars()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deterministic_advisory_planner_strategy() -> None:
    event = SecurityEvent(
        id="evt-1",
        tenant_id="default",
        type="manual.consultation",
        severity="low",
        payload={"goal": "Как обеспечить безопасность мультиагентной системы?"},
        correlation_id="eng-advisory",
    )
    engagement = Engagement(id="eng-advisory", tenant_id="default", goal=event.payload["goal"])
    detector = PlannerSignalDetector(payload=event.payload)
    context = PlannerContext(
        event=event,
        engagement=engagement,
        goal=str(event.payload["goal"]),
        available=["consultant", "soc"],
        signals=detector.as_dict(),
        detector=detector,
        planner_pack=PlannerPack(persona="planner"),
        profile=ProfilePack(id="cybersec-soc", name="cybersec-soc"),
    )
    plan = await DeterministicAdvisoryPlannerStrategy().plan(context)
    assert plan is not None
    assert plan.personas == ["consultant"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_planner_router_skips_llm_for_advisory() -> None:
    event = SecurityEvent(
        id="evt-2",
        tenant_id="default",
        type="manual.consultation",
        severity="low",
        payload={"goal": "How do we harden CI/CD pipelines?"},
        correlation_id="eng-advisory-2",
    )
    engagement = Engagement(id="eng-advisory-2", tenant_id="default", goal=event.payload["goal"])
    detector = PlannerSignalDetector(payload=event.payload)
    context = PlannerContext(
        event=event,
        engagement=engagement,
        goal=str(event.payload["goal"]),
        available=["consultant", "soc"],
        signals=detector.as_dict(),
        detector=detector,
        planner_pack=PlannerPack(persona="planner"),
        profile=ProfilePack(id="cybersec-soc", name="cybersec-soc"),
    )

    class _FailLlm:
        async def plan(self, ctx: PlannerContext) -> EngagementPlan | None:
            raise AssertionError("LLM planner should not run for advisory goals")

    plan = await PlannerRouter().route(context, _FailLlm())
    assert plan.personas == ["consultant"]
