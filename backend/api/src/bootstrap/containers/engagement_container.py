from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bootstrap.container import Container


class EngagementContainer:
    """Owns engagement lifecycle and event routing/dispatch for the api service.

    This is api's own copy of worker's bootstrap/containers/engagement_container.py,
    trimmed to the methods api's use-cases actually call — no orchestrator/
    bus-consumer wiring (get_worker_orchestrator, get_run_worker_job,
    get_agent_runtime, get_bus_ingress_router, wire_bus_router, wire_bus_reload
    stay worker-only). Meta-LLM planning (cys_core.application.use_cases.meta_planner)
    is worker-only too — it needs the real agent runtime, which must never be
    constructed in api. StartEngagement never builds a MetaPlanner here; for
    PlanStrategy.META_LLM it enqueues a WorkerJob(persona="planner",
    work_kind="engagement_plan") and returns — worker's RunWorkerJob recognizes
    that job and runs EngagementPlannerRunner (the real planner, with the real
    runtime) instead. See docs/MSP_BACKLOG.md §1.2.
    """

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._start_engagement = None
        self._event_router = None
        self._route_event = None
        self._route_and_enqueue = None
        self._event_ingress = None
        self._dispatch_event = None
        self._engagement_bus_guard = None
        self._orchestration = None

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
        from cys_core.application.use_cases.update_plan_quality import UpdatePlanQuality

        container = self._container
        metrics = container.get_metrics_port()
        plan_quality = UpdatePlanQuality(
            container.get_plan_catalog(), mutation=container.get_catalog_mutation_service()
        )
        self._route_event = RouteEvent(
            self.get_event_router(),
            record_event_ingested=metrics.record_event_ingested,
            record_plan_match=lambda plan_id, _rule_idx, jobs: plan_quality.record_match(plan_id, jobs=jobs),
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

    def publish_hitl_resolved(self, **kwargs) -> None:
        from cys_core.infrastructure.engagement.hitl_egress import publish_hitl_resolved

        publish_hitl_resolved(self._container.get_engagement_egress(), **kwargs)

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

