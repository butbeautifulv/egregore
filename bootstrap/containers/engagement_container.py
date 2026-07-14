from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cys_core.application.ports.bus import AgentTransportConnector
    from cys_core.application.ports.job_queue import JobQueueConnector
    from cys_core.application.ports.sandbox import SandboxConnector

    from bootstrap.container import Container


class EngagementContainer:
    """Owns engagement lifecycle, event routing/dispatch, and worker/bus orchestration wiring.

    This is the largest cluster in the original god object: everything that
    constructs or coordinates around an "engagement" (event routing,
    dispatch, worker job pipelines, meta-planning, HITL bus guard,
    orchestration/enqueue). Cross-domain dependencies (catalog, persistence,
    observability, tools, auth) are reached via ``self._container`` — the
    parent ``Container`` facade — exactly as the original methods reached
    sibling getters via ``self`` before the split.
    """

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._bus_router = None
        self._start_engagement = None
        self._meta_planner = None
        self._orchestration = None
        self._event_router = None
        self._route_event = None
        self._route_and_enqueue = None
        self._event_ingress = None
        self._dispatch_event = None
        self._worker_orchestrators: dict[str | None, Any] = {}
        self._engagement_bus_guard = None
        self._plan_investigation = None

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

    def get_event_router(self):
        if self._event_router is not None:
            return self._event_router
        from cys_core.application.routing.event_router import EventRouter

        container = self._container
        self._event_router = EventRouter.from_plans_dir(
            container.get_agents_root_port().agents_root() / "plans",
            policy_port=container.get_profile_policy_port(),
            plan_catalog=container.get_plan_catalog(),
        )
        return self._event_router

    def get_route_event(self):
        if self._route_event is not None:
            return self._route_event
        from cys_core.application.use_cases.route_event import RouteEvent

        container = self._container
        metrics = container.get_metrics_port()
        self._route_event = RouteEvent(
            self.get_event_router(),
            plan_catalog=container.get_plan_catalog(),
            record_event_ingested=metrics.record_event_ingested,
            mutation=container.get_catalog_mutation_service(),
        )
        return self._route_event

    def get_dispatch_event(self):
        if self._dispatch_event is not None:
            return self._dispatch_event
        from cys_core.application.use_cases.dispatch_event import DispatchEvent

        self._dispatch_event = DispatchEvent(
            route_event=self.get_route_event(),
            enqueuer=self.get_orchestration_port(),
            application_tracing=self._container.get_application_tracing_port(),
        )
        return self._dispatch_event

    def get_route_and_enqueue(self):
        if self._route_and_enqueue is not None:
            return self._route_and_enqueue
        from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
        from cys_core.infrastructure.kafka_events import publish_raw_event, publish_raw_event_sync

        container = self._container
        metrics = container.get_metrics_port()
        self._route_and_enqueue = RouteAndEnqueueEvent(
            route_event=self.get_route_event(),
            enqueuer=self.get_orchestration_port(),
            correlation_id_port=container.get_correlation_id_port(),
            use_kafka=self.settings.use_kafka,
            publish_raw_event_sync=publish_raw_event_sync,
            publish_raw_event=publish_raw_event,
            record_event_ingested=metrics.record_event_ingested,
            application_tracing=container.get_application_tracing_port(),
        )
        return self._route_and_enqueue

    def get_event_ingress(self):
        if self._event_ingress is not None:
            return self._event_ingress
        from interfaces.ingress.router import EventIngress

        self._event_ingress = EventIngress(route_and_enqueue=self.get_route_and_enqueue())
        return self._event_ingress

    def get_worker_orchestrator(self, persona: str | None = None):
        if persona not in self._worker_orchestrators:
            from interfaces.worker.orchestrator import WorkerOrchestrator

            self._worker_orchestrators[persona] = WorkerOrchestrator(persona=persona)
        return self._worker_orchestrators[persona]

    def get_run_worker_job(
        self,
        persona: str | None = None,
        *,
        runtime=None,
        registry=None,
        bus=None,
        sandbox: "SandboxConnector | None" = None,
        transport: "AgentTransportConnector | None" = None,
        queue: "JobQueueConnector | None" = None,
        sanitizer=None,
    ):
        from cys_core.application.workers.pipeline_builder import WorkerPipelineDeps, build_worker_pipeline
        from cys_core.domain.security.factory import get_input_sanitizer
        from cys_core.infrastructure.bus_transport import get_bus_transport
        from cys_core.infrastructure.memory.factory import get_memory_read_service, get_memory_write_service
        from cys_core.infrastructure.queue import get_job_queue
        from cys_core.infrastructure.sandbox import get_sandbox_connector
        from cys_core.registry.mcp_tools import mcp_tool_registry
        from cys_core.registry.skills_tool import make_load_skill_tool
        from cys_core.registry.tools import tool_registry

        container = self._container
        metrics = container.get_metrics_port()
        runtime = runtime or self.get_agent_runtime()
        sandbox = sandbox or get_sandbox_connector()
        transport = transport or get_bus_transport()
        queue = queue or get_job_queue(persona=persona, settings=self.settings)
        sanitizer = sanitizer or get_input_sanitizer()
        if bus is None:
            from interfaces.worker.orchestrator import build_agent_bus

            bus = build_agent_bus(signing_key=self.settings.bus_signing_key_bytes)

        return build_worker_pipeline(
            WorkerPipelineDeps(
                engagement_store=self.get_engagement_state_store(),
                memory_reader=get_memory_read_service(self.settings),
                memory_writer=get_memory_write_service(self.settings),
                metrics=metrics,
                runtime=runtime,
                schema_registry=container.get_schema_registry_port(),
                bus=bus,
                transport=transport,
                queue=queue,
                job_store=container.get_job_store(),
                agent_catalog=container.get_agent_catalog(),
                engagement_egress=self.get_engagement_egress(),
                bus_guard=self.get_engagement_bus_guard(),
                agent_registry=registry or container.get_agent_registry_port(),
                sandbox=sandbox,
                sanitizer=sanitizer,
                worker_tracing=container.get_worker_tracing_port(),
                use_tool_gateway=self.settings.use_tool_gateway,
                dev_schema_bypass=self.settings.stage == "dev",
                resolve_mcp_tools=mcp_tool_registry.resolve,
                resolve_legacy_tools=tool_registry.resolve,
                make_load_skill_tool=make_load_skill_tool,
                meta_planner=self.get_meta_planner(),
                dispatch=self.get_dispatch_event(),
                workspace_store=container.get_workspace_store(),
            )
        )

    def get_agent_runtime(self):
        return self.get_worker_orchestrator().runtime

    def get_meta_planner(self):
        if self._meta_planner is not None:
            return self._meta_planner
        from cys_core.application.use_cases.meta_planner import MetaPlanner
        from cys_core.runtime.agent import get_runtime

        container = self._container
        self._meta_planner = MetaPlanner(
            runtime=get_runtime(),
            engagement_store=self.get_engagement_state_store(),
            resource_source=container.get_resource_source_port(),
            persona_ranking=container.get_persona_ranking_port(),
            agent_catalog=container.get_agent_catalog(),
            application_tracing=container.get_application_tracing_port(),
        )
        return self._meta_planner

    def wire_engagement_egress(self) -> None:
        from cys_core.infrastructure.engagement.factory import reset_engagement_egress_cache

        reset_engagement_egress_cache()

    def get_start_engagement(self):
        if self._start_engagement is not None:
            return self._start_engagement
        from cys_core.application.use_cases.start_engagement import StartEngagement

        container = self._container
        self._start_engagement = StartEngagement(
            engagement_store=self.get_engagement_state_store(),
            dispatch=self.get_dispatch_event(),
            egress=self.get_engagement_egress(),
            meta_planner=self.get_meta_planner(),
            correlation_id_port=container.get_correlation_id_port(),
            trace_flush_port=container.get_trace_flush_port(),
            application_tracing=container.get_application_tracing_port(),
        )
        return self._start_engagement

    def get_engagement_state_store(self):
        from cys_core.infrastructure.engagement.store_factory import get_engagement_state_store

        return get_engagement_state_store(self.settings)

    def get_engagement_egress(self):
        from cys_core.infrastructure.engagement.factory import get_engagement_egress

        return get_engagement_egress(self.settings)

    def get_reconcile_stuck_engagements(self):
        from cys_core.application.use_cases.enqueue_synthesis_job import EnqueueSynthesisJob
        from cys_core.application.use_cases.reconcile_stuck_engagements import ReconcileStuckEngagements

        container = self._container
        settings = self.settings
        return ReconcileStuckEngagements(
            engagement_store=self.get_engagement_state_store(),
            job_store=container.get_job_store(),
            enqueue_synthesis_job=EnqueueSynthesisJob(
                engagement_store=self.get_engagement_state_store(),
                queue=container.get_job_queue(),
                job_store=container.get_job_store(),
                engagement_egress=self.get_engagement_egress(),
            ),
            queue=container.get_job_queue(),
            enqueue_worker_jobs=self.get_orchestration_port(),
            metrics=container.get_metrics_port(),
            default_job_timeout_s=settings.worker_job_timeout,
            synth_job_timeout_s=settings.worker_job_timeout_synth or settings.worker_job_timeout,
            planner_timeout_seconds=settings.planner_timeout_seconds,
            synthesis_stale_multiplier=settings.reconcile_synthesis_stale_multiplier,
            scan_limit=settings.reconcile_scan_limit,
        )

    def get_bus_ingress_router(self):
        if self._bus_router is not None:
            return self._bus_router
        from interfaces.control_plane.bus_router_wiring import build_bus_ingress_router

        # build_bus_ingress_router expects the full Container API surface
        # (get_orchestration_port, get_engagement_egress, get_bus_dedup_store,
        # get_engagement_bus_guard, get_metrics_port), so pass the parent
        # container, not this sub-container, exactly as before the split.
        self._bus_router = build_bus_ingress_router(self._container)
        return self._bus_router

    def wire_bus_router(self) -> None:
        from cys_core.infrastructure.bus_transport import DELIVERY_TOPIC, get_bus_transport

        router = self.get_bus_ingress_router()
        transport = get_bus_transport()

        async def _on_delivery(envelope: dict) -> None:
            await router.route_envelope(envelope)

        transport.subscribe(DELIVERY_TOPIC, _on_delivery)

    def get_orchestration_port(self):
        if self._orchestration is not None:
            return self._orchestration
        from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs

        container = self._container
        cfg = self.bus_guard_config()
        self._orchestration = EnqueueWorkerJobs(
            queue=container.get_job_queue(),
            job_store=container.get_job_store(),
            engagement_store=self.get_engagement_state_store(),
            bus_guard=self.get_engagement_bus_guard(),
            metrics=container.get_metrics_port(),
            max_jobs_per_engagement=cfg.max_jobs_per_engagement,
            max_revisions_per_persona=self.settings.bus_max_revisions_per_persona,
        )
        return self._orchestration

    def get_plan_investigation(self):
        if self._plan_investigation is not None:
            return self._plan_investigation
        from cys_core.application.use_cases.plan_investigation import PlanInvestigation

        container = self._container
        self._plan_investigation = PlanInvestigation(
            runtime=self.get_agent_runtime(),
            engagement_store=self.get_engagement_state_store(),
            resource_source=container.get_resource_source_port(),
            persona_ranking=container.get_persona_ranking_port(),
            agent_catalog=container.get_agent_catalog(),
            application_tracing=container.get_application_tracing_port(),
            engagement_egress=self.get_engagement_egress(),
        )
        return self._plan_investigation

    def wire_bus_reload(self) -> None:
        from cys_core.infrastructure.catalog.catalog_registry import register_bus_reload_callback
        from interfaces.worker.orchestrator import build_agent_bus

        def _reload_bus(_registry: object) -> None:
            build_agent_bus(signing_key=self.settings.bus_signing_key_bytes)

        register_bus_reload_callback(_reload_bus)
