from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bootstrap.container import Container


class EngagementContainer:
    """Owns engagement state store/egress wiring.

    Trimmed from worker's copy for the standalone tool-gateway package (see
    docs/MSP_BACKLOG.md §21.6): the worker job pipeline/meta-
    planning/bus-ingress-routing/event-routing methods this class originally
    also owned are gone — none of them are reachable from
    interfaces/gateways/tool/. Cross-domain dependencies (catalog,
    persistence, observability, tools, auth) are reached via
    ``self._container`` — the parent ``Container`` facade — exactly as the
    original methods reached sibling getters via ``self`` before the split.
    """

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._engagement_bus_guard = None

    @property
    def settings(self):
        return self._container.settings

    def bus_guard_config(self):
        from cys_core.application.bus_guard_config import BusGuardConfig

        s = self.settings
        return BusGuardConfig(
            max_total_jobs_window=s.bus_max_total_jobs_window,
            dedup_trip_threshold=s.bus_dedup_trip_threshold,
            pingpong_trip_threshold=s.bus_pingpong_trip_threshold,
            noop_churn_threshold=s.bus_noop_churn_threshold,
            guard_window_seconds=s.bus_guard_window_seconds,
            redis_url=s.redis_url,
            max_jobs_per_engagement=s.bus_max_jobs_per_engagement,
        )

    def get_engagement_bus_guard(self):
        if self._engagement_bus_guard is None:
            from cys_core.application.engagement_bus_guard import (
                EngagementBusGuard,
                configure_engagement_bus_guard,
            )

            self._engagement_bus_guard = EngagementBusGuard(config=self.bus_guard_config())
            configure_engagement_bus_guard(self._engagement_bus_guard)
        return self._engagement_bus_guard

    # get_event_router/get_route_event/get_dispatch_event/get_orchestration_port
    # (worker's copy) are the event-ingress -> job-enqueue pipeline
    # (EventRouter/RouteEvent/DispatchEvent/EnqueueWorkerJobs) — api/worker's
    # ingestion path, not reachable from interfaces/gateways/tool/. Removed,
    # along with get_job_store() (persistence_container.py) and
    # platform_gauges.py, whose only callers were this cluster. See
    # docs/MSP_BACKLOG.md §21.6.

    # get_worker_orchestrator/get_run_worker_job/get_agent_runtime/
    # get_meta_planner (worker's copy) construct and run the full agent-
    # execution job pipeline (WorkerOrchestrator, build_worker_pipeline,
    # MetaPlanner, cys_core.runtime.agent) — none of it is reachable from
    # interfaces/gateways/tool/, which only ever needs
    # get_tool_execution_gateway()'s much smaller InvokeTool chain. Removed
    # entirely rather than left as unreachable-but-present code, since ty
    # check has no way to know these methods are never called and flags
    # their imports (langchain_core, cys_core.runtime, cys_core.llm) as
    # unresolved once those packages/modules aren't part of this package.
    # See docs/MSP_BACKLOG.md §21.6.

    def wire_engagement_egress(self) -> None:
        from cys_core.infrastructure.engagement.factory import reset_engagement_egress_cache

        reset_engagement_egress_cache()

    def get_engagement_state_store(self):
        from cys_core.infrastructure.engagement.store_factory import get_engagement_state_store

        return get_engagement_state_store(self.settings)

    def get_engagement_egress(self):
        from cys_core.infrastructure.engagement.factory import get_engagement_egress

        return get_engagement_egress(self.settings)

    # get_bus_ingress_router/wire_bus_router (worker's copy) wire the
    # inter-agent bus ingress path (interfaces.control_plane.bus_router_wiring)
    # — control-plane/worker concern, not reachable from the gateway. Removed,
    # same reasoning as above.

    # get_plan_investigation (needs get_agent_runtime(), removed above) and
    # wire_bus_reload (interfaces.worker.orchestrator.build_agent_bus) are
    # likewise worker/agent-runtime-only. Removed.
