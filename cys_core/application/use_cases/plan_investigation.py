from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from pydantic import BaseModel, Field

from bootstrap.settings import settings
from cys_core.application.ports.memory import InvestigationStateStore
from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.memory.models import InvestigationState

logger = logging.getLogger(__name__)


class InvestigationPlan(BaseModel):
    personas: list[str] = Field(default_factory=list)
    sub_goals: dict[str, str] = Field(default_factory=dict)
    rationale: str = ""


class PlannerRuntime(Protocol):
    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        tenant_id: str | None = None,
        investigation_id: str | None = None,
    ) -> dict[str, Any]: ...


class PlanInvestigation:
    """LLM planner for manual.investigation events — produces ordered persona plan."""

    AVAILABLE_PERSONAS = ["soc", "network", "compliance", "consultant", "redteam"]

    def __init__(
        self,
        *,
        runtime: PlannerRuntime,
        investigation_store: InvestigationStateStore,
        planner_persona: str = "planner",
    ) -> None:
        self.runtime = runtime
        self.investigation_store = investigation_store
        self.planner_persona = planner_persona

    @classmethod
    def fallback_personas(cls) -> list[str]:
        raw = settings.planner_fallback_personas.strip()
        if not raw:
            return ["consultant"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _investigation_id(self, event: SecurityEvent) -> str:
        return event.correlation_id or event.id

    def _goal_from_event(self, event: SecurityEvent) -> str:
        return str(event.payload.get("goal", event.payload.get("message", "Investigate security incident")))

    def _fallback_plan(self, goal: str, *, rationale: str) -> InvestigationPlan:
        personas = self.fallback_personas()
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

        prompt = json.dumps(
            {
                "goal": goal,
                "event_type": event.type,
                "severity": event.severity,
                "available_personas": self.AVAILABLE_PERSONAS,
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
            )
            plan = self._parse_plan(result, goal)
            if not plan.personas:
                plan = self._fallback_plan(goal, rationale="fallback_default_plan")
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
        }
