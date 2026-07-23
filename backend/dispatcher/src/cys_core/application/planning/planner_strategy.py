from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from cys_core.application.planning.signals import PlannerSignalDetector
from cys_core.domain.catalog.models import PlannerPack, ProfilePack
from cys_core.domain.engagement.models import Engagement, EngagementPlan
from cys_core.domain.events.models import SecurityEvent


@dataclass(frozen=True)
class PlannerContext:
    event: SecurityEvent
    engagement: Engagement
    goal: str
    available: list[str]
    signals: dict[str, bool]
    detector: PlannerSignalDetector
    planner_pack: PlannerPack
    profile: ProfilePack


class PlannerStrategy(Protocol):
    async def plan(self, context: PlannerContext) -> EngagementPlan | None:
        """Return a plan when this strategy applies, or None to defer."""


class DeterministicAdvisoryPlannerStrategy:
    """Product policy: advisory goals route directly to consultant without planner LLM."""

    async def plan(self, context: PlannerContext) -> EngagementPlan | None:
        if not context.signals.get("advisory"):
            return None
        if context.signals.get("incident_id_present"):
            return None
        if "consultant" not in set(context.available):
            return None
        return EngagementPlan(
            personas=["consultant"],
            sub_goals={"consultant": context.goal},
            rationale="Advisory goal — consultant-only plan (deterministic routing).",
            depends_on={},
        )


class PlannerRouter:
    def __init__(self, *, advisory: PlannerStrategy | None = None) -> None:
        self._advisory = advisory or DeterministicAdvisoryPlannerStrategy()

    async def route(self, context: PlannerContext, llm_plan: PlannerStrategy) -> EngagementPlan:
        advisory_plan = await self._advisory.plan(context)
        if advisory_plan is not None:
            return advisory_plan
        llm_result = await llm_plan.plan(context)
        if llm_result is None:
            raise RuntimeError("LLM planner strategy returned None")
        return llm_result
