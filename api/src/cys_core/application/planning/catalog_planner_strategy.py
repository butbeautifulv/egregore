from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from cys_core.application.engagement_streaming import publish_assistant_snapshot
from cys_core.application.errors import PlanningFailedError
from cys_core.application.planning.post_processors import apply_post_processors
from cys_core.application.planning.prompt_builder import CatalogPlannerPromptBuilder
from cys_core.application.planning.runtime import PlannerRuntime
from cys_core.application.planning.signals import PlannerSignalDetector
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.persona_ranking import PersonaRankingPort
from cys_core.application.ports.resource_source import ResourceSourcePort
from cys_core.application.ports.stream_context import StreamContext
from cys_core.application.ports.tracing_ports import NOOP_APPLICATION_TRACING, ApplicationTracingPort
from cys_core.application.runtime_config import (
    get_max_planner_personas,
    get_planner_default_execution_mode,
    get_planner_default_post_processors,
    get_planner_fallback_personas,
)
from cys_core.domain.catalog.models import PlannerPack, ProfilePack
from cys_core.domain.engagement.models import Engagement, EngagementPlan, EngagementStatus, ExecutionMode
from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.parsing.json_text import parse_json_text, parse_loose_structured_text

logger = logging.getLogger(__name__)

_DEFAULT_POST_PROCESSORS = ["advisory_consultant_fallback", "staged_soc_intel_for_incident"]


def _default_post_processors() -> list[str]:
    raw = get_planner_default_post_processors()
    parsed = [p.strip() for p in raw.split(",") if p.strip()]
    return parsed or list(_DEFAULT_POST_PROCESSORS)


class CatalogPlannerStrategy:
    """Catalog-driven planner: prompt, signals, and post-processors from ProfilePack."""

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
        reload_personas: Callable[[], None] | None = None,
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
        self._reload_personas = reload_personas

    def _profile_pack(self) -> ProfilePack:
        for profile in self.agent_catalog.list_profiles():
            if profile.id == self.profile_id:
                return profile
        return ProfilePack(id=self.profile_id, name=self.profile_id)

    def _planner_pack(self, profile: ProfilePack) -> PlannerPack:
        if profile.planner is not None:
            return profile.planner
        return PlannerPack(
            persona=self.planner_persona,
            post_processors=_default_post_processors(),
            synthesis_default="consultant",
        )

    def _available_personas(self) -> list[str]:
        personas = self.resource_source.list_worker_personas(profile_id=self.profile_id)
        if personas:
            return personas
        if self._reload_personas is not None:
            self._reload_personas()
        return self.resource_source.list_worker_personas(profile_id=self.profile_id)

    def _max_personas(self) -> int:
        return max(1, get_max_planner_personas())

    def _cap_personas(self, personas: list[str]) -> list[str]:
        limit = self._max_personas()
        return list(personas[:limit]) if len(personas) > limit else list(personas)

    @staticmethod
    def _parse_execution_mode(raw: Any) -> ExecutionMode | None:
        if raw is None or raw == "":
            return None
        value = str(raw).strip().lower()
        if value == ExecutionMode.PARALLEL:
            return ExecutionMode.PARALLEL
        if value == ExecutionMode.STAGED:
            return ExecutionMode.STAGED
        return None

    def _finalize_plan(self, plan: EngagementPlan, synthesis_default: str) -> EngagementPlan:
        if len(plan.personas) == 1:
            plan.execution_mode = ExecutionMode.PARALLEL
            if plan.personas[0] == "consultant":
                plan.synthesis_persona = None
            else:
                plan.synthesis_persona = plan.synthesis_persona or synthesis_default
            return plan
        if plan.execution_mode is None:
            default_mode = get_planner_default_execution_mode().strip().lower()
            plan.execution_mode = (
                ExecutionMode.STAGED if default_mode == ExecutionMode.STAGED else ExecutionMode.PARALLEL
            )
        if not plan.synthesis_persona:
            plan.synthesis_persona = synthesis_default
        return plan

    def _build_fallback_plan(self, goal: str, available: list[str], *, reason: str) -> EngagementPlan:
        allowed = set(available)
        personas = [p.strip() for p in get_planner_fallback_personas().split(",") if p.strip()]
        personas = [persona for persona in personas if persona in allowed]
        if not personas:
            if "consultant" in allowed:
                personas = ["consultant"]
            elif available:
                personas = [available[0]]
            else:
                personas = ["consultant"]
        personas = self._cap_personas(personas)
        return EngagementPlan(
            personas=personas,
            sub_goals={persona: goal for persona in personas},
            rationale=f"Planner fallback after LLM error. Using: {', '.join(personas)}.",
            depends_on={},
        )

    def _parse_plan(self, result: dict[str, Any], goal: str) -> EngagementPlan:
        if not isinstance(result, dict):
            raise PlanningFailedError("planner", "planner returned non-object response")
        if result.get("error"):
            raise PlanningFailedError("planner", str(result["error"]))
        response_text = result.get("response")
        if isinstance(response_text, str) and response_text.strip():
            parsed = parse_loose_structured_text(response_text) or parse_json_text(response_text)
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
            synthesis_raw = result.get("synthesis_persona")
            synthesis_persona = str(synthesis_raw).strip() if synthesis_raw else None
            reasoning_steps = result.get("reasoning_steps")
            return EngagementPlan(
                personas=personas,
                sub_goals=sub_goals,
                depends_on=result.get("depends_on", {}) if isinstance(result.get("depends_on"), dict) else {},
                rationale=str(result.get("rationale", "")),
                execution_mode=self._parse_execution_mode(result.get("execution_mode")),
                synthesis_persona=synthesis_persona or None,
                reasoning_steps=[str(step) for step in reasoning_steps] if isinstance(reasoning_steps, list) else [],
                plan_status=str(result.get("plan_status", "")),
            )
        raw = result.get("raw_response", "")
        if raw:
            parsed = parse_loose_structured_text(str(raw)) or parse_json_text(str(raw))
            if parsed is not None and "personas" in parsed:
                return self._parse_plan(parsed, goal)
            snippet = str(raw)[:500]
            raise PlanningFailedError("planner", f"unparseable planner response: {snippet}" if snippet else "")
        raise PlanningFailedError("planner", "planner returned empty response")

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
            execution_mode=plan.execution_mode.value if plan.execution_mode else None,
            synthesis_persona=plan.synthesis_persona,
            planner_sub_goals=plan.sub_goals,
            planner_depends_on=plan.depends_on,
        )

    async def execute(self, event: SecurityEvent) -> EngagementPlan:
        goal = str(event.payload.get("goal", event.payload.get("message", "Investigate security incident")))
        engagement_id = event.correlation_id or event.id
        intake = event.payload.get("intake")
        intake_dict = intake if isinstance(intake, dict) else {}
        with self._tracing.span(
            "engagement.plan",
            event_type=event.type,
            engagement_id=engagement_id,
            tenant_id=event.tenant_id,
        ):
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
            elif engagement.planner_status != "planning":
                engagement.planner_status = "planning"
                engagement.planner_error = ""
                self.engagement_store.upsert(engagement)

            profile = self._profile_pack()
            planner_pack = self._planner_pack(profile)
            available = self._available_personas()
            detector = PlannerSignalDetector(payload=event.payload, intake=intake_dict)
            signals = detector.as_dict()
            prompt = CatalogPlannerPromptBuilder(profile=profile, planner=planner_pack).build(
                goal=goal,
                event_type=event.type,
                severity=event.severity,
                personas=available,
                max_personas=self._max_personas(),
                signals=signals,
            )
            try:
                result = await self.runtime.arun(
                    planner_pack.persona or self.planner_persona,
                    prompt,
                    session_id=f"planner:{engagement_id}",
                    tenant_id=event.tenant_id,
                    investigation_id=engagement_id,
                    profile_id=self.profile_id,
                    job_id=f"planner:{engagement_id}",
                    stream_context=StreamContext(
                        engagement_id=engagement_id,
                        job_id=f"planner:{engagement_id}",
                        persona=planner_pack.persona or self.planner_persona,
                        tenant_id=event.tenant_id,
                    ),
                )
                plan = self._parse_plan(result, goal)
                plan = apply_post_processors(
                    plan,
                    planner_pack.post_processors or _DEFAULT_POST_PROCESSORS,
                    signals=signals,
                    available=available,
                    goal=goal,
                )
                if not plan.personas:
                    raise PlanningFailedError(engagement_id, "planner returned empty personas list")
                requested = list(plan.personas)
                allowed = set(available)
                plan.personas = [persona for persona in plan.personas if persona in allowed]
                if not plan.personas:
                    raise PlanningFailedError(engagement_id, f"planner personas not in catalog: {requested}")
                ranked = self.persona_ranking.rank(plan.personas, profile_id=self.profile_id)
                plan.personas = self._cap_personas(ranked)
                plan = self._finalize_plan(plan, planner_pack.synthesis_default)
                self._apply_plan_to_engagement(engagement, plan, status="ok")
                if self._engagement_egress is not None:
                    publish_assistant_snapshot(
                        egress=self._engagement_egress,
                        engagement_id=engagement_id,
                        job_id=f"planner:{engagement_id}",
                        persona=planner_pack.persona or self.planner_persona,
                        tenant_id=event.tenant_id,
                        text=json.dumps(
                            {
                                "personas": plan.personas,
                                "sub_goals": plan.sub_goals,
                                "rationale": plan.rationale,
                                "depends_on": plan.depends_on,
                                "execution_mode": plan.execution_mode.value if plan.execution_mode else None,
                                "synthesis_persona": plan.synthesis_persona,
                            },
                            indent=2,
                            ensure_ascii=False,
                        ),
                    )
                logger.info(
                    "catalog_planner succeeded for %s: personas=%s mode=%s synthesis=%s",
                    engagement_id,
                    plan.personas,
                    plan.execution_mode,
                    plan.synthesis_persona,
                )
                return plan
            except PlanningFailedError as exc:
                self._apply_plan_to_engagement(
                    engagement,
                    EngagementPlan(personas=[], sub_goals={}, rationale=""),
                    status="error",
                    error=str(exc),
                )
                raise
            except Exception as exc:
                logger.warning("Catalog planner failed for %s: %s — using fallback personas", engagement_id, exc)
                plan = self._build_fallback_plan(goal, available, reason=str(exc))
                plan = apply_post_processors(
                    plan,
                    planner_pack.post_processors or _DEFAULT_POST_PROCESSORS,
                    signals=signals,
                    available=available,
                    goal=goal,
                )
                plan = self._finalize_plan(plan, planner_pack.synthesis_default)
                self._apply_plan_to_engagement(
                    engagement,
                    plan,
                    status="fallback",
                    error=str(exc),
                )
                if self._engagement_egress is not None:
                    publish_assistant_snapshot(
                        egress=self._engagement_egress,
                        engagement_id=engagement_id,
                        job_id=f"planner:{engagement_id}",
                        persona=planner_pack.persona or self.planner_persona,
                        tenant_id=event.tenant_id,
                        text=json.dumps(
                            {
                                "personas": plan.personas,
                                "sub_goals": plan.sub_goals,
                                "rationale": plan.rationale,
                                "depends_on": plan.depends_on,
                                "execution_mode": plan.execution_mode.value if plan.execution_mode else None,
                                "synthesis_persona": plan.synthesis_persona,
                                "planner_fallback": True,
                            },
                            indent=2,
                            ensure_ascii=False,
                        ),
                    )
                return plan
