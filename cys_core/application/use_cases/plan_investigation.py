from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from pydantic import BaseModel, Field

from cys_core.application.advisory_goal import is_advisory_goal
from cys_core.application.policy_resolver import get_profile_policy_resolver
from cys_core.application.runtime_config import get_planner_fallback_personas, get_use_dynamic_catalog
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.hybrid_registry import get_agent_catalog
from cys_core.registry.discovery_tools import rank_personas_by_quality
from cys_core.application.ports.memory import InvestigationStateStore
from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.memory.models import InvestigationState

logger = logging.getLogger(__name__)


class InvestigationPlan(BaseModel):
    personas: list[str] = Field(default_factory=list)
    sub_goals: dict[str, str] = Field(default_factory=dict)
    rationale: str = ""
    depends_on: dict[str, list[str]] = Field(default_factory=dict)
    reasoning_steps: list[str] = Field(default_factory=list)
    plan_status: str = ""


class PlannerRuntime(Protocol):
    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        tenant_id: str | None = None,
        investigation_id: str | None = None,
        profile_id: str | None = None,
    ) -> dict[str, Any]: ...


class PlanInvestigation:
    """LLM planner for manual.investigation events — produces ordered persona plan."""

    def __init__(
        self,
        *,
        runtime: PlannerRuntime,
        investigation_store: InvestigationStateStore,
        planner_persona: str = "planner",
        profile_id: str = "cybersec-soc",
    ) -> None:
        self.runtime = runtime
        self.investigation_store = investigation_store
        self.planner_persona = planner_persona
        self.profile_id = profile_id

    def _available_personas(self) -> list[str]:
        from cys_core.application.resource_source import get_resource_source

        return get_resource_source().list_worker_personas(profile_id=self.profile_id)

    @classmethod
    def fallback_personas(cls, *, profile_id: str = DEFAULT_PROFILE_ID) -> list[str]:
        return get_profile_policy_resolver().planner_fallback_personas(
            profile_id,
            env_csv=get_planner_fallback_personas(),
        )

    def _investigation_id(self, event: SecurityEvent) -> str:
        return event.correlation_id or event.id

    def _goal_from_event(self, event: SecurityEvent) -> str:
        return str(event.payload.get("goal", event.payload.get("message", "Investigate security incident")))

    def _fallback_plan(self, goal: str, *, rationale: str) -> InvestigationPlan:
        personas = self.fallback_personas(profile_id=self.profile_id)
        return InvestigationPlan(
            personas=personas,
            sub_goals={persona: goal for persona in personas},
            rationale=rationale,
        )

    def _parse_plan(self, result: dict[str, Any], goal: str) -> InvestigationPlan:
        if "personas" in result and isinstance(result["personas"], list):
            personas = [str(item) for item in result["personas"]]
            sub_goals = result.get("sub_goals", {})
            if not isinstance(sub_goals, dict):
                sub_goals = {}
            return InvestigationPlan(
                personas=personas,
                sub_goals={str(k): str(v) for k, v in sub_goals.items()},
                rationale=str(result.get("rationale", "")),
                reasoning_steps=[str(s) for s in result.get("reasoning_steps", []) if s],
                plan_status=str(result.get("plan_status", "")),
            )
        raw = result.get("raw_response", "")
        if raw:
            try:
                parsed = json.loads(raw)
                return self._parse_plan(parsed, goal)
            except json.JSONDecodeError:
                pass
        return self._fallback_plan(goal, rationale="fallback_default_plan")

    def begin_planning(self, event: SecurityEvent) -> InvestigationState:
        """Create or update investigation state before async planner runs."""
        goal = self._goal_from_event(event)
        investigation_id = self._investigation_id(event)
        state = self.investigation_store.get(event.tenant_id, investigation_id)
        if state is None:
            state = InvestigationState(
                investigation_id=investigation_id,
                tenant_id=event.tenant_id,
                goal=goal,
                status="in_progress",
            )
        state.goal = goal
        state.status = "in_progress"
        state.planner_status = "planning"
        state.planner_plan = None
        state.planner_rationale = ""
        state.planner_error = ""
        self.investigation_store.upsert(state)
        return state

    def _apply_plan_to_state(self, state: InvestigationState, plan: InvestigationPlan, *, status: str, error: str = "") -> None:
        state.planner_plan = plan.personas
        state.planner_status = status  # type: ignore[assignment]
        state.planner_rationale = plan.rationale
        state.planner_error = error
        state.goal = state.goal or ""
        if state.status == "open":
            state.status = "in_progress"
        self.investigation_store.upsert(state)

    async def execute(self, event: SecurityEvent) -> InvestigationPlan:
        goal = self._goal_from_event(event)
        investigation_id = self._investigation_id(event)
        state = self.investigation_store.get(event.tenant_id, investigation_id)
        if state is None:
            state = self.begin_planning(event)
        elif state.planner_status != "planning":
            state.planner_status = "planning"
            state.planner_error = ""
            self.investigation_store.upsert(state)

        if is_advisory_goal(goal):
            plan = InvestigationPlan(
                personas=["consultant"],
                sub_goals={"consultant": goal},
                rationale="advisory_fast_path_consultant_only",
            )
            self._apply_plan_to_state(state, plan, status="ok")
            return plan

        available = self._available_personas()
        prompt = json.dumps(
            {
                "goal": goal,
                "event_type": event.type,
                "severity": event.severity,
                "available_personas": available,
                "instructions": (
                    "Return JSON with keys: personas (ordered list), sub_goals (map persona->task), rationale. "
                    "Use consultant alone for general IB advisory questions."
                ),
            },
            ensure_ascii=False,
        )
        try:
            result = await self.runtime.arun(
                self.planner_persona,
                prompt,
                session_id=f"planner:{investigation_id}",
                tenant_id=event.tenant_id,
                investigation_id=investigation_id,
                profile_id=self.profile_id,
            )
            plan = self._parse_plan(result, goal)
            if not plan.personas:
                plan = self._fallback_plan(goal, rationale="fallback_default_plan")
            allowed = set(available)
            plan.personas = [persona for persona in plan.personas if persona in allowed]
            if not plan.personas:
                plan = self._fallback_plan(goal, rationale="planner_invalid_personas_fallback")
            plan.personas = rank_personas_by_quality(
                plan.personas, catalog=get_agent_catalog(), profile_id=self.profile_id
            )
            self._apply_plan_to_state(state, plan, status="ok")
        except Exception as exc:
            logger.warning("Planner failed for %s: %s", investigation_id, exc)
            plan = self._fallback_plan(goal, rationale="planner_unavailable_fallback")
            self._apply_plan_to_state(state, plan, status="fallback", error=str(exc))

        return plan

    def to_worker_jobs_payload(self, plan: InvestigationPlan) -> dict[str, Any]:
        return {
            "planner_plan": plan.personas,
            "sub_goals": plan.sub_goals,
            "rationale": plan.rationale,
            "depends_on": plan.depends_on,
        }
