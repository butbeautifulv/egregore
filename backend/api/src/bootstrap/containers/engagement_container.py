from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bootstrap.container import Container


class EngagementContainer:
    """Owns engagement lifecycle and event routing/dispatch for the api service.

    This is api's own copy of worker's bootstrap/containers/engagement_container.py,
    trimmed to the methods api's use-cases actually call — no orchestrator/
    bus-consumer wiring (get_worker_orchestrator, get_run_worker_job,
    get_agent_runtime, get_bus_ingress_router, wire_bus_router, wire_bus_reload
    stay worker-only). See plan §1.2/§3: get_meta_planner()/
    get_plan_investigation() pass runtime=None here — the real agent runtime
    (cys_core.runtime.agent) pulls in most of what Phase B moved to worker/,
    and duplicating that into api/ too was rejected as a worse cost than the
    accepted regression (meta-LLM async planning, gated behind
    ENGAGEMENT_ASYNC_PLANNING which defaults to true, stops working from the
    api build until a real fix moves it to be genuinely worker-side).
    """

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._start_engagement = None
        self._meta_planner = None
        self._event_router = None
        self._route_event = None
        self._route_and_enqueue = None
        self._event_ingress = None
        self._dispatch_event = None
        self._engagement_bus_guard = None
        self._orchestration = None
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

    def get_meta_planner(self):
        if self._meta_planner is not None:
            return self._meta_planner
        from cys_core.application.use_cases.meta_planner import MetaPlanner

        container = self._container
        # runtime=None: see module docstring — the real agent runtime is not
        # available in the api build. Safe as long as the sync PlanInvestigation
        # path (self.runtime.arun(...) in catalog_planner_strategy.py) is never
        # actually reached from here; if it ever is, this raises immediately
        # (AttributeError) instead of silently doing the wrong thing.
        self._meta_planner = MetaPlanner(
            runtime=None,
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
        from cys_core.infrastructure.catalog.catalog_registry import reload_agent_registry

        container = self._container
        # runtime=None — see get_meta_planner() above.
        self._plan_investigation = PlanInvestigation(
            runtime=None,
            engagement_store=self.get_engagement_state_store(),
            resource_source=container.get_resource_source_port(),
            persona_ranking=container.get_persona_ranking_port(),
            agent_catalog=container.get_agent_catalog(),
            application_tracing=container.get_application_tracing_port(),
            engagement_egress=self.get_engagement_egress(),
            reload_personas=reload_agent_registry,
        )
        return self._plan_investigation
