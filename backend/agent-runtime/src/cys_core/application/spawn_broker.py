from __future__ import annotations

import uuid

from cys_core.application.policy_resolver import get_profile_policy_resolver
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.profile_policy import ProfilePolicyPort
from cys_core.application.ports.workspace_store import WorkspaceStorePort
from cys_core.domain.agents.control import is_platform_readonly_persona
from cys_core.domain.runs.mode_policy import ModePolicy
from cys_core.domain.runs.models import InteractionMode
from cys_core.domain.runs.spawn import MAX_SPAWN_DEPTH, SpawnWorkerPayload
from cys_core.domain.workers.models import WorkerJob


class SubagentSpawnBroker:
    """Validate and materialize spawn_worker requests into WorkerJobs."""

    def __init__(
        self,
        catalog: AgentCatalogPort,
        *,
        max_spawn_depth: int | None = None,
        policy_port: ProfilePolicyPort | None = None,
        workspace_store: WorkspaceStorePort | None = None,
        require_workspace_in_enforce: bool = False,
    ) -> None:
        self._catalog = catalog
        self._max_spawn_depth_override = max_spawn_depth
        self._policy_port = policy_port
        self._workspace_store = workspace_store
        self._require_workspace_in_enforce = require_workspace_in_enforce

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
        workspace_id: str = "",
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
            spawn_targets: set[str] = set()
            if conductor and conductor.capabilities:
                spawn_targets = {
                    cap for cap in conductor.capabilities if cap not in ("spawn_worker", "conductor")
                }
                if spawn_targets and payload.persona not in spawn_targets:
                    return "persona_not_in_conductor_capabilities"
            ws_id = (workspace_id or "").strip()
            if not ws_id and self._require_workspace_in_enforce:
                return "workspace_required_in_enforce"
            if ws_id and self._workspace_store is not None:
                forked = {a.name for a in self._workspace_store.list_agents(ws_id)}
                if payload.persona in forked or is_platform_readonly_persona(payload.persona):
                    pass
                elif forked:
                    return "persona_not_in_workspace"
                elif not is_platform_readonly_persona(payload.persona):
                    return "persona_not_in_workspace"
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
            profile_id=payload.parent_context.profile_id,
        )
