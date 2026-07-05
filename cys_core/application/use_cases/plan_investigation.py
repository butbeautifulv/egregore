from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from cys_core.application.engagement_streaming import publish_assistant_snapshot
from cys_core.application.errors import PlanningFailedError
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.persona_ranking import PersonaRankingPort
from cys_core.application.ports.resource_source import ResourceSourcePort
from cys_core.application.ports.tracing_ports import ApplicationTracingPort, NOOP_APPLICATION_TRACING
from cys_core.application.ports.stream_context import StreamContext
from cys_core.domain.engagement.models import Engagement, EngagementPlan, EngagementStatus
from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.parsing.json_text import parse_json_text

logger = logging.getLogger(__name__)

MAX_PLANNER_PERSONAS = 3


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
        job_id: str | None = None,
        stream_context: StreamContext | None = None,
    ) -> dict[str, Any]: ...


class PlanInvestigation:
    """LLM planner for engagement meta-LLM strategy — produces ordered persona plan."""

    def __init__(
        self,
        *,
        runtime: PlannerRuntime,
        engagement_store: EngagementStateStore,
        resource_source: ResourceSourcePort,
        persona_ranking: PersonaRankingPort,
        agent_catalog: AgentCatalogPort,
        planner_persona: str = "planner",
        profile_id: str = "cybersec-soc",
        application_tracing: ApplicationTracingPort | None = None,
        engagement_egress: EngagementEgressPort | None = None,
    ) -> None:
        self.runtime = runtime
        self.engagement_store = engagement_store
        self.resource_source = resource_source
        self.persona_ranking = persona_ranking
        self.agent_catalog = agent_catalog
        self.planner_persona = planner_persona
        self.profile_id = profile_id
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING
        self._engagement_egress = engagement_egress

    def _available_personas(self) -> list[str]:
        return self.resource_source.list_worker_personas(profile_id=self.profile_id)

    def _engagement_id(self, event: SecurityEvent) -> str:
        return event.correlation_id or event.id

    def _goal_from_event(self, event: SecurityEvent) -> str:
        return str(event.payload.get("goal", event.payload.get("message", "Investigate security incident")))

    def _cap_personas(self, personas: list[str]) -> list[str]:
        if len(personas) <= MAX_PLANNER_PERSONAS:
            return list(personas)
        return list(personas[:MAX_PLANNER_PERSONAS])

    @staticmethod
    def _raw_snippet(result: dict[str, Any]) -> str:
        raw = str(result.get("raw_response", ""))
        return raw[:500] if raw else ""

    def _parse_plan(self, result: dict[str, Any], goal: str) -> EngagementPlan:
        if not isinstance(result, dict):
            raise PlanningFailedError("planner", "planner returned non-object response")

        if result.get("error"):
            raise PlanningFailedError("planner", str(result["error"]))

        response_text = result.get("response")
        if isinstance(response_text, str) and response_text.strip():
            parsed = parse_json_text(response_text)
            if parsed is not None:
                return self._parse_plan(parsed, goal)

        if "personas" in result and isinstance(result["personas"], list):
            personas = [str(item) for item in result["personas"]]
            sub_goals = result.get("sub_goals", {})
            if isinstance(sub_goals, list):
                sub_goals = (
                    {persona: str(item) for persona, item in zip(personas, sub_goals, strict=False)}
                    if personas
                    else {}
                )
            elif not isinstance(sub_goals, dict):
                sub_goals = {}
            if not sub_goals and personas:
                sub_goals = {persona: goal for persona in personas}
            return EngagementPlan(
                personas=personas,
                sub_goals={str(k): str(v) for k, v in sub_goals.items()},
                rationale=str(result.get("rationale", "")),
                reasoning_steps=[str(s) for s in result.get("reasoning_steps", []) if s],
                plan_status=str(result.get("plan_status", "")),
            )

        raw = result.get("raw_response", "")
        if raw:
            parsed = parse_json_text(str(raw))
            if parsed is not None and "personas" in parsed:
                return self._parse_plan(parsed, goal)
            snippet = self._raw_snippet(result)
            raise PlanningFailedError(
                "planner",
                f"unparseable planner response{f': {snippet}' if snippet else ''}",
            )

        raise PlanningFailedError("planner", "planner returned empty response")

    def begin_planning(self, event: SecurityEvent) -> Engagement:
        """Create or update engagement state before async planner runs."""
        goal = self._goal_from_event(event)
        engagement_id = self._engagement_id(event)
        engagement = self.engagement_store.get(event.tenant_id, engagement_id)
        if engagement is None:
            engagement = Engagement(
                id=engagement_id,
                tenant_id=event.tenant_id,
                goal=goal,
                status=EngagementStatus.PLANNING,
                correlation_id=engagement_id,
            )
        engagement.begin_planning(goal=goal)
        self.engagement_store.upsert(engagement)
        return engagement

    def _apply_plan_to_engagement(
        self,
        engagement: Engagement,
        plan: EngagementPlan,
        *,
        status: str,
        error: str = "",
    ) -> None:
        self.engagement_store.update_planner_state(
            engagement.tenant_id,
            engagement.id,
            planner_plan=plan.personas,
            planner_status=status,
            planner_rationale=plan.rationale,
            planner_error=error,
            goal=engagement.goal or None,
        )

    def _apply_planning_error(self, engagement: Engagement, message: str) -> None:
        self._apply_plan_to_engagement(
            engagement,
            EngagementPlan(personas=[], sub_goals={}, rationale=""),
            status="error",
            error=message,
        )

    async def execute(self, event: SecurityEvent) -> EngagementPlan:
        goal = self._goal_from_event(event)
        engagement_id = self._engagement_id(event)
        with self._tracing.span(
            "engagement.plan",
            event_type=event.type,
            engagement_id=engagement_id,
            tenant_id=event.tenant_id,
        ):
            return await self._execute_plan(event, goal, engagement_id)

    async def _execute_plan(self, event: SecurityEvent, goal: str, engagement_id: str) -> EngagementPlan:
        engagement = self.engagement_store.get(event.tenant_id, engagement_id)
        if engagement is None:
            engagement = self.begin_planning(event)
        elif engagement.planner_status != "planning":
            engagement.planner_status = "planning"
            engagement.planner_error = ""
            self.engagement_store.upsert(engagement)

        available = self._available_personas()
        prompt = (
            f"Goal: {goal}\n"
            f"Event type: {event.type}\n"
            f"Severity: {event.severity}\n"
            f"Available personas: {', '.join(available)}\n"
            "Select up to 3 personas. Use consultant alone for general IB advisory or consultation. "
            "Use network (+ optional compliance) for LAN hardening and segmentation questions."
        )
        try:
            result = await self.runtime.arun(
                self.planner_persona,
                prompt,
                session_id=f"planner:{engagement_id}",
                tenant_id=event.tenant_id,
                investigation_id=engagement_id,
                profile_id=self.profile_id,
                job_id=f"planner:{engagement_id}",
                stream_context=StreamContext(
                    engagement_id=engagement_id,
                    job_id=f"planner:{engagement_id}",
                    persona=self.planner_persona,
                    tenant_id=event.tenant_id,
                ),
            )
            plan = self._parse_plan(result, goal)
            if not plan.personas:
                raise PlanningFailedError(engagement_id, "planner returned empty personas list")

            requested = list(plan.personas)
            allowed = set(available)
            plan.personas = [persona for persona in plan.personas if persona in allowed]
            if not plan.personas:
                raise PlanningFailedError(
                    engagement_id,
                    f"planner personas not in catalog: {requested}",
                )

            ranked = self.persona_ranking.rank(plan.personas, profile_id=self.profile_id)
            if len(ranked) > MAX_PLANNER_PERSONAS:
                logger.warning(
                    "Planner personas truncated from %d to %d for %s",
                    len(ranked),
                    MAX_PLANNER_PERSONAS,
                    engagement_id,
                )
            plan.personas = self._cap_personas(ranked)
            self._apply_plan_to_engagement(engagement, plan, status="ok")
            if self._engagement_egress is not None:
                publish_assistant_snapshot(
                    egress=self._engagement_egress,
                    engagement_id=engagement_id,
                    job_id=f"planner:{engagement_id}",
                    persona=self.planner_persona,
                    tenant_id=event.tenant_id,
                    text=json.dumps(
                        {
                            "personas": plan.personas,
                            "sub_goals": plan.sub_goals,
                            "rationale": plan.rationale,
                            "depends_on": plan.depends_on,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                )
            logger.info(
                "planner succeeded for %s: personas=%s rationale=%s",
                engagement_id,
                plan.personas,
                plan.rationale,
            )
            return plan
        except PlanningFailedError as exc:
            self._apply_planning_error(engagement, str(exc))
            raise
        except Exception as exc:
            logger.warning("Planner failed for %s: %s", engagement_id, exc)
            self._apply_planning_error(engagement, str(exc))
            raise PlanningFailedError(engagement_id, str(exc)) from exc

    def to_worker_jobs_payload(self, plan: EngagementPlan) -> dict[str, Any]:
        return {
            "planner_plan": plan.personas,
            "sub_goals": plan.sub_goals,
            "rationale": plan.rationale,
            "depends_on": plan.depends_on,
        }
