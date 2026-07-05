from __future__ import annotations

import uuid
from typing import Any

from cys_core.application.policy_resolver import get_profile_policy_resolver
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.profile_policy import ProfilePolicyPort
from cys_core.domain.runs.mode_policy import ModePolicy
from cys_core.domain.runs.models import InteractionMode, RunContext
from cys_core.domain.runs.plan_models import WorkPlan
from cys_core.domain.runs.spawn import MAX_SPAWN_DEPTH, SpawnWorkerPayload
from cys_core.domain.runs.state_models import RunState, RunStatus
from cys_core.domain.workers.models import WorkerJob


class SubagentSpawnBroker:
    """Validate and materialize spawn_worker requests into WorkerJobs."""

    def __init__(
        self,
        catalog: AgentCatalogPort,
        *,
        max_spawn_depth: int | None = None,
        policy_port: ProfilePolicyPort | None = None,
    ) -> None:
        self._catalog = catalog
        self._max_spawn_depth_override = max_spawn_depth
        self._policy_port = policy_port

    def _resolve_max_spawn_depth(self, profile_id: str) -> int:
        if self._max_spawn_depth_override is not None:
            return self._max_spawn_depth_override
        if self._policy_port is not None:
            return self._policy_port.get_max_spawn_depth(profile_id)
        return get_profile_policy_resolver().max_spawn_depth(profile_id)

    def _resolve_trust_floor(self, profile_id: str) -> float:
        if self._policy_port is None:
            raise RuntimeError("Profile policy port required for SubagentSpawnBroker")
        return self._policy_port.get_trust_floor(profile_id)

    def validate(
        self,
        payload: SpawnWorkerPayload,
        *,
        mode: InteractionMode | None,
        profile_id: str = "cybersec-soc",
        parent_persona: str = "",
    ) -> str | None:
        if not ModePolicy.allow_spawn(mode):
            return "spawn_not_allowed_in_mode"
        max_depth = self._resolve_max_spawn_depth(profile_id)
        if payload.parent_context.spawn_depth >= max_depth or payload.parent_context.spawn_depth >= MAX_SPAWN_DEPTH:
            return "max_spawn_depth_exceeded"
        agent = self._catalog.get_agent(payload.persona)
        if agent is None or not agent.enabled:
            return "unknown_persona"
        if parent_persona == "conductor":
            conductor = self._catalog.get_agent("conductor")
            if conductor and conductor.capabilities:
                spawn_targets = {cap for cap in conductor.capabilities if cap not in ("spawn_worker", "conductor")}
                if spawn_targets and payload.persona not in spawn_targets:
                    return "persona_not_in_conductor_capabilities"
        floor = self._resolve_trust_floor(agent.profile_id)
        if agent.quality.empirical_trust < floor:
            return "persona_quality_below_floor"
        return None

    def to_worker_job(self, payload: SpawnWorkerPayload, *, event_id: str = "") -> WorkerJob:
        child = payload.parent_context.spawn_child(f"job-{uuid.uuid4().hex[:12]}", persona=payload.persona)
        return WorkerJob(
            job_id=child.context_id,
            event_id=event_id or child.context_id,
            persona=payload.persona,
            payload={
                "sub_goal": payload.sub_goal,
                "persona_overlay": payload.persona_overlay,
                "spawn_depth": child.spawn_depth,
                "parent_correlation_key": payload.parent_context.correlation_key,
            },
            correlation_id=payload.parent_context.context_id,
            tenant_id=payload.parent_context.tenant_id,
        )
