from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bootstrap.settings import Settings, get_settings
from cys_core.application.policy_enforcement import PolicyEnforcementService
from cys_core.application.policy_resolver import (
    ProfilePolicyResolver,
    configure_policy_resolver_from_settings,
)
from cys_core.application.runtime_config import configure_from_settings
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog, reload_agent_registry
from cys_core.infrastructure.catalog.profile_policy import (
    ProfilePolicyLoader,
    get_breaker_config,
    get_bus_policy,
    get_cost_per_1k_tokens,
    get_escalation_paths,
    get_hitl_threshold,
    get_max_spawn_depth,
    get_notify_control_severities,
    get_profile_policy,
    get_trust_floor,
)
from cys_core.infrastructure.catalog.registry_factory import (
    get_catalog_audit,
    get_catalog_write_gate,
    get_mcp_catalog,
    get_plan_catalog,
    get_skill_catalog,
    get_tool_catalog,
)

if TYPE_CHECKING:
    from cys_core.application.ports import PersistenceContext
    from cys_core.application.ports.bus import AgentTransportConnector
    from cys_core.application.ports.job_queue import JobQueueConnector
    from cys_core.application.ports.memory import EpisodicMemoryStore
    from cys_core.application.ports.sandbox import SandboxConnector


class Container:
    """Composition root for infrastructure connectors, catalog ports, and policy wiring."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        configure_from_settings(self.settings)
        from cys_core.infrastructure.observability.metrics_adapter import build_metrics_port

        self._policy_loader = ProfilePolicyLoader(get_agent_catalog)
        self._resolver = configure_policy_resolver_from_settings(
            self.settings,
            policy_loader=self._policy_loader,
            metrics_port=build_metrics_port(),
        )
        self._enforcement = PolicyEnforcementService(self._resolver)
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
        self._tool_chain_policy = None
        self._invoke_tool = None
        self._tool_execution_gateway = None
        self._agent_registry_port = None
        self._schema_registry_port = None
        self._tool_registry_port = None
        self._persona_ranking_port = None
        self._skill_registry_port = None
        self._resource_source_port = None
        self._agents_root_port = None
        self._datasource_catalog_port = None
        self._datasource_audit_port = None
        self._policy_merge_port = None
        self._context_summarizer = None
        self._reflexion_store = None
        self._catalog_mutation_service = None
        self._plan_investigation = None
        self._metrics_port = None
        self._correlation_id_port = None
        self._worker_tracing_port = None
        self._trace_flush_port = None
        self._product_pack_port = None
        self._catalog_seed_loaders_port = None
        self._policy_defaults_port = None
        self._application_settings_port = None
        self._engagement_bus_guard = None
        self._bus_dedup_store = None

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

    def get_bus_dedup_store(self):
        if self._bus_dedup_store is None:
            from cys_core.infrastructure.bus_dedup_store import get_bus_dedup_store

            self._bus_dedup_store = get_bus_dedup_store(
                redis_url=self.settings.redis_url,
                strict_redis=self.settings.strict_redis_queue,
            )
        return self._bus_dedup_store

    def get_metrics_port(self):
        if self._metrics_port is None:
            from cys_core.infrastructure.observability.metrics_adapter import build_metrics_port

            self._metrics_port = build_metrics_port()
        return self._metrics_port

    def get_correlation_id_port(self):
        if self._correlation_id_port is None:
            from cys_core.infrastructure.observability.tracing_adapter import build_correlation_id_port

            self._correlation_id_port = build_correlation_id_port()
        return self._correlation_id_port

    def get_worker_tracing_port(self):
        if self._worker_tracing_port is None:
            from cys_core.infrastructure.observability.worker_tracing_adapter import build_worker_tracing_port

            self._worker_tracing_port = build_worker_tracing_port(self.get_trace_backend)
        return self._worker_tracing_port

    def get_application_tracing_port(self):
        return self.get_worker_tracing_port()

    def get_trace_flush_port(self):
        if self._trace_flush_port is None:
            from cys_core.infrastructure.observability.trace_flush_adapter import build_trace_flush_port

            self._trace_flush_port = build_trace_flush_port()
        return self._trace_flush_port

    def get_product_pack_port(self):
        if self._product_pack_port is None:
            from cys_core.infrastructure.bootstrap.product_pack_adapter import build_product_pack_port

            self._product_pack_port = build_product_pack_port()
        return self._product_pack_port

    def get_catalog_seed_loaders_port(self):
        if self._catalog_seed_loaders_port is None:
            from cys_core.infrastructure.bootstrap.catalog_seed_adapter import build_catalog_seed_loaders_port

            self._catalog_seed_loaders_port = build_catalog_seed_loaders_port()
        return self._catalog_seed_loaders_port

    def get_policy_defaults_port(self):
        if self._policy_defaults_port is None:
            from cys_core.infrastructure.bootstrap.policy_defaults_adapter import build_policy_defaults_port

            self._policy_defaults_port = build_policy_defaults_port()
        return self._policy_defaults_port

    def get_application_settings_port(self):
        if self._application_settings_port is None:
            from cys_core.infrastructure.bootstrap.application_settings_adapter import build_application_settings_port

            self._application_settings_port = build_application_settings_port()
        return self._application_settings_port

    def get_tool_chain_policy(self):
        if self._tool_chain_policy is not None:
            return self._tool_chain_policy
        from cys_core.application.tools.tool_chain_policy import ToolChainPolicy

        self._tool_chain_policy = ToolChainPolicy(max_high_risk_depth=self.settings.max_high_risk_tool_chain_depth)
        return self._tool_chain_policy

    def get_invoke_tool(self):
        if self._invoke_tool is not None:
            return self._invoke_tool
        from cys_core.application.use_cases.invoke_tool import InvokeTool
        from cys_core.infrastructure.tools.adapters import invoke_adapter
        from cys_core.infrastructure.tools.audit import configure_tool_audit, record_tool_invocation
        from cys_core.infrastructure.tools.sanitize import sanitize_tool_output_or_raise
        from cys_core.observability.metrics import metrics
        from cys_core.registry.mcp_tools import require_sandbox

        self._invoke_tool = InvokeTool(
            require_sandbox=require_sandbox,
            check_tool_chain=self.get_tool_chain_policy().check,
            invoke_adapter=invoke_adapter,
            tool_registry=self.get_tool_registry_port(),
            sanitize_tool_output_or_raise=sanitize_tool_output_or_raise,
            record_tool_invocation=record_tool_invocation,
            record_tool_metric=lambda name, ok: metrics.record_tool_invocation(name, success=ok),
            application_tracing=self.get_application_tracing_port(),
        )
        return self._invoke_tool

    def get_tool_execution_gateway(self):
        if self._tool_execution_gateway is not None:
            return self._tool_execution_gateway
        from cys_core.infrastructure.tools.local_gateway import build_local_tool_execution_gateway

        self._tool_execution_gateway = build_local_tool_execution_gateway(self.get_invoke_tool())
        return self._tool_execution_gateway

    def get_event_router(self):
        if self._event_router is not None:
            return self._event_router
        from cys_core.application.routing.event_router import EventRouter

        self._event_router = EventRouter.from_plans_dir(
            self.get_agents_root_port().agents_root() / "plans",
            policy_port=self.get_profile_policy_port(),
            plan_catalog=self.get_plan_catalog(),
        )
        return self._event_router

    def get_route_event(self):
        if self._route_event is not None:
            return self._route_event
        from cys_core.application.use_cases.route_event import RouteEvent

        metrics = self.get_metrics_port()
        self._route_event = RouteEvent(
            self.get_event_router(),
            plan_catalog=self.get_plan_catalog(),
            record_event_ingested=metrics.record_event_ingested,
            mutation=self.get_catalog_mutation_service(),
        )
        return self._route_event

    def get_dispatch_event(self):
        if self._dispatch_event is not None:
            return self._dispatch_event
        from cys_core.application.use_cases.dispatch_event import DispatchEvent

        self._dispatch_event = DispatchEvent(
            route_event=self.get_route_event(),
            enqueuer=self.get_orchestration_port(),
            application_tracing=self.get_application_tracing_port(),
        )
        return self._dispatch_event

    def get_route_and_enqueue(self):
        if self._route_and_enqueue is not None:
            return self._route_and_enqueue
        from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
        from cys_core.infrastructure.kafka_events import publish_raw_event, publish_raw_event_sync

        metrics = self.get_metrics_port()
        self._route_and_enqueue = RouteAndEnqueueEvent(
            route_event=self.get_route_event(),
            enqueuer=self.get_orchestration_port(),
            correlation_id_port=self.get_correlation_id_port(),
            use_kafka=self.settings.use_kafka,
            publish_raw_event_sync=publish_raw_event_sync,
            publish_raw_event=publish_raw_event,
            record_event_ingested=metrics.record_event_ingested,
            application_tracing=self.get_application_tracing_port(),
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
        sandbox: SandboxConnector | None = None,
        transport: AgentTransportConnector | None = None,
        queue: JobQueueConnector | None = None,
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

        metrics = self.get_metrics_port()
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
                schema_registry=self.get_schema_registry_port(),
                bus=bus,
                transport=transport,
                queue=queue,
                job_store=self.get_job_store(),
                agent_catalog=self.get_agent_catalog(),
                engagement_egress=self.get_engagement_egress(),
                bus_guard=self.get_engagement_bus_guard(),
                agent_registry=registry or self.get_agent_registry_port(),
                sandbox=sandbox,
                sanitizer=sanitizer,
                worker_tracing=self.get_worker_tracing_port(),
                use_tool_gateway=self.settings.use_tool_gateway,
                dev_schema_bypass=self.settings.stage == "dev",
                resolve_mcp_tools=mcp_tool_registry.resolve,
                resolve_legacy_tools=tool_registry.resolve,
                make_load_skill_tool=make_load_skill_tool,
            )
        )

    def get_agent_runtime(self):
        return self.get_worker_orchestrator().runtime

    def get_meta_planner(self):
        if self._meta_planner is not None:
            return self._meta_planner
        from cys_core.application.use_cases.meta_planner import MetaPlanner

        self._meta_planner = MetaPlanner(
            runtime=self.get_agent_runtime(),
            engagement_store=self.get_engagement_state_store(),
            resource_source=self.get_resource_source_port(),
            persona_ranking=self.get_persona_ranking_port(),
            agent_catalog=self.get_agent_catalog(),
            application_tracing=self.get_application_tracing_port(),
        )
        return self._meta_planner

    def wire_engagement_egress(self) -> None:
        from cys_core.infrastructure.engagement.factory import reset_engagement_egress_cache

        reset_engagement_egress_cache()

    def get_start_engagement(self):
        if self._start_engagement is not None:
            return self._start_engagement
        from cys_core.application.use_cases.start_engagement import StartEngagement

        self._start_engagement = StartEngagement(
            engagement_store=self.get_engagement_state_store(),
            dispatch=self.get_dispatch_event(),
            egress=self.get_engagement_egress(),
            meta_planner=self.get_meta_planner(),
            correlation_id_port=self.get_correlation_id_port(),
            trace_flush_port=self.get_trace_flush_port(),
            application_tracing=self.get_application_tracing_port(),
        )
        return self._start_engagement

    def get_engagement_state_store(self):
        from cys_core.infrastructure.engagement.store_factory import get_engagement_state_store

        return get_engagement_state_store(self.settings)

    def get_engagement_egress(self):
        from cys_core.infrastructure.engagement.factory import get_engagement_egress

        return get_engagement_egress(self.settings)

    def get_bus_ingress_router(self):
        if self._bus_router is not None:
            return self._bus_router
        from interfaces.control_plane.bus_router_wiring import build_bus_ingress_router

        self._bus_router = build_bus_ingress_router(self)
        return self._bus_router

    def wire_bus_router(self) -> None:
        from cys_core.infrastructure.bus_transport import DELIVERY_TOPIC, get_bus_transport

        router = self.get_bus_ingress_router()
        transport = get_bus_transport()

        async def _on_delivery(envelope: dict) -> None:
            await router.route_envelope(envelope)

        transport.subscribe(DELIVERY_TOPIC, _on_delivery)

    def get_job_queue(self, persona: str | None = None) -> JobQueueConnector:
        from cys_core.infrastructure.queue import get_job_queue

        return get_job_queue(persona=persona, settings=self.settings)

    def get_bus_transport(self) -> AgentTransportConnector:
        from cys_core.infrastructure.bus_transport import get_bus_transport

        return get_bus_transport(settings=self.settings)

    def get_sandbox_connector(self) -> SandboxConnector:
        from cys_core.infrastructure.sandbox import get_sandbox_connector

        return get_sandbox_connector(settings=self.settings)

    def get_persistence_context(self) -> PersistenceContext:
        from cys_core.persistence import get_persistence_connector

        return get_persistence_connector(self.settings.persistence_connector).open()

    async def get_async_persistence_context(self) -> PersistenceContext:
        from cys_core.persistence import get_persistence_connector

        connector = get_persistence_connector(self.settings.persistence_connector)
        return await connector.open_async()

    def get_job_store(self):
        from interfaces.control_plane.job_store import get_job_store

        return get_job_store(self.settings)

    def get_orchestration_port(self):
        if self._orchestration is not None:
            return self._orchestration
        from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs

        cfg = self.bus_guard_config()
        self._orchestration = EnqueueWorkerJobs(
            queue=self.get_job_queue(),
            job_store=self.get_job_store(),
            engagement_store=self.get_engagement_state_store(),
            bus_guard=self.get_engagement_bus_guard(),
            metrics=self.get_metrics_port(),
            max_jobs_per_engagement=cfg.max_jobs_per_engagement,
        )
        return self._orchestration

    def get_episodic_memory_store(self) -> EpisodicMemoryStore:
        from cys_core.infrastructure.memory.factory import get_episodic_memory_store

        return get_episodic_memory_store(self.settings)

    def get_memory_read_service(self):
        from cys_core.infrastructure.memory.factory import get_memory_read_service

        return get_memory_read_service(self.settings)

    def get_memory_write_service(self):
        from cys_core.infrastructure.memory.factory import get_memory_write_service

        return get_memory_write_service(self.settings)

    def get_attachment_store(self):
        from cys_core.infrastructure.runs.factory import get_attachment_store

        return get_attachment_store()

    def get_catalog_version(self) -> int:
        from cys_core.infrastructure.catalog.catalog_registry import get_catalog_version_metric

        return get_catalog_version_metric()

    def get_seed_catalog(self):
        from bootstrap.catalog_loader import load_profile_pack
        from cys_core.application.use_cases.seed_catalog import SeedCatalog
        from cys_core.infrastructure.catalog.tool_catalog_seed import load_tools_for_seed

        return SeedCatalog(
            self.get_agent_catalog(),
            tool_catalog=self.get_tool_catalog(),
            seed_loaders=self.get_catalog_seed_loaders_port(),
            load_profile_pack=load_profile_pack,
            load_tools_for_seed=load_tools_for_seed,
            reload=self.reload_catalog,
            mutation=self.get_catalog_mutation_service(),
        )

    def get_trace_backend(self):
        from bootstrap.observability_factory import build_trace_backend, resolve_trace_backend_name

        return build_trace_backend(resolve_trace_backend_name(self.settings), cfg=self.settings)

    def get_prompt_backend(self):
        from bootstrap.observability_factory import build_prompt_backend

        return build_prompt_backend(self.settings.obs_prompt_backend)

    def get_judge_backend(self):
        from bootstrap.observability_factory import build_judge_backend

        name = "langfuse" if self.settings.critic_use_llm_judge else self.settings.obs_judge_backend
        return build_judge_backend(name)

    def get_eval_backend(self):
        from bootstrap.observability_factory import build_eval_backend

        return build_eval_backend(self.settings.obs_eval_backend)

    def get_prompt_resolver(self):
        from cys_core.application.observability.prompt_resolver import PromptResolver

        return PromptResolver(self.get_prompt_backend())

    def get_token_verifier(self):
        from cys_core.infrastructure.auth.factory import build_token_verifier

        return build_token_verifier(self.settings)

    def get_agent_catalog(self):
        return get_agent_catalog()

    def get_skill_catalog(self):
        return get_skill_catalog()

    def get_plan_catalog(self):
        return get_plan_catalog()

    def get_mcp_catalog(self):
        return get_mcp_catalog()

    def get_tool_catalog(self):
        return get_tool_catalog()

    def get_catalog_write_gate(self):
        return get_catalog_write_gate()

    def get_catalog_audit(self):
        return get_catalog_audit()

    def get_agent_registry_port(self):
        if self._agent_registry_port is not None:
            return self._agent_registry_port
        from cys_core.infrastructure.registry.agent_registry_adapter import build_agent_registry_port

        self._agent_registry_port = build_agent_registry_port()
        return self._agent_registry_port

    def get_schema_registry_port(self):
        if self._schema_registry_port is not None:
            return self._schema_registry_port
        from cys_core.infrastructure.registry.schema_registry_adapter import build_schema_registry_port

        self._schema_registry_port = build_schema_registry_port()
        return self._schema_registry_port

    def get_tool_registry_port(self):
        if self._tool_registry_port is not None:
            return self._tool_registry_port
        from cys_core.infrastructure.registry.tool_registry_adapter import build_tool_registry_port

        self._tool_registry_port = build_tool_registry_port()
        return self._tool_registry_port

    def get_persona_ranking_port(self):
        if self._persona_ranking_port is not None:
            return self._persona_ranking_port
        from cys_core.infrastructure.catalog.persona_ranking import build_persona_ranking_port

        self._persona_ranking_port = build_persona_ranking_port(
            catalog=self.get_agent_catalog(),
            policy_port=self.get_profile_policy_port(),
        )
        return self._persona_ranking_port

    def get_skill_registry_port(self):
        if self._skill_registry_port is not None:
            return self._skill_registry_port
        from cys_core.infrastructure.registry.skill_registry_adapter import build_skill_registry_port

        self._skill_registry_port = build_skill_registry_port()
        return self._skill_registry_port

    def get_resource_source_port(self):
        if self._resource_source_port is not None:
            return self._resource_source_port
        from cys_core.infrastructure.registry.resource_source_adapter import build_resource_source_port

        self._resource_source_port = build_resource_source_port(self.get_agent_registry_port())
        return self._resource_source_port

    def get_agents_root_port(self):
        if self._agents_root_port is not None:
            return self._agents_root_port
        from cys_core.infrastructure.registry.agents_root_adapter import build_agents_root_port

        self._agents_root_port = build_agents_root_port()
        return self._agents_root_port

    def get_datasource_catalog_port(self):
        if self._datasource_catalog_port is not None:
            return self._datasource_catalog_port
        from cys_core.infrastructure.datasources.catalog_adapter import build_datasource_catalog_port

        self._datasource_catalog_port = build_datasource_catalog_port()
        return self._datasource_catalog_port

    def get_datasource_audit_port(self):
        if self._datasource_audit_port is not None:
            return self._datasource_audit_port
        from cys_core.infrastructure.datasources.audit_adapter import build_datasource_audit_port

        self._datasource_audit_port = build_datasource_audit_port()
        return self._datasource_audit_port

    def get_policy_merge_port(self):
        if self._policy_merge_port is not None:
            return self._policy_merge_port
        from cys_core.infrastructure.catalog.policy_merge_adapter import build_policy_merge_port

        self._policy_merge_port = build_policy_merge_port()
        return self._policy_merge_port

    def get_context_summarizer(self):
        if self._context_summarizer is not None:
            return self._context_summarizer
        from cys_core.infrastructure.context.factory import get_context_summarizer

        self._context_summarizer = get_context_summarizer()
        return self._context_summarizer

    def get_reflexion_store(self):
        if self._reflexion_store is not None:
            return self._reflexion_store
        from cys_core.infrastructure.reflexion.memory import get_reflexion_store

        self._reflexion_store = get_reflexion_store()
        return self._reflexion_store

    def get_catalog_mutation_service(self):
        if self._catalog_mutation_service is not None:
            return self._catalog_mutation_service
        from cys_core.application.catalog_mutation_service import CatalogMutationService

        self._catalog_mutation_service = CatalogMutationService(
            write_gate=get_catalog_write_gate(reload=self.reload_catalog),
            agent_catalog=self.get_agent_catalog(),
            tool_catalog=self.get_tool_catalog(),
            audit=self.get_catalog_audit(),
            reload=self.reload_catalog,
        )
        return self._catalog_mutation_service

    def get_plan_investigation(self):
        if self._plan_investigation is not None:
            return self._plan_investigation
        from cys_core.application.use_cases.plan_investigation import PlanInvestigation

        self._plan_investigation = PlanInvestigation(
            runtime=self.get_agent_runtime(),
            engagement_store=self.get_engagement_state_store(),
            resource_source=self.get_resource_source_port(),
            persona_ranking=self.get_persona_ranking_port(),
            agent_catalog=self.get_agent_catalog(),
            application_tracing=self.get_application_tracing_port(),
            engagement_egress=self.get_engagement_egress(),
        )
        return self._plan_investigation

    def get_profile_policy_port(self) -> ProfilePolicyLoader:
        return self._policy_loader

    def get_policy_resolver(self) -> ProfilePolicyResolver:
        return self._resolver

    def get_policy_enforcement(self) -> PolicyEnforcementService:
        return self._enforcement

    def reload_catalog(self) -> None:
        reload_agent_registry()

    def wire_hitl_pause(self) -> None:
        from cys_core.infrastructure.kafka_paused import publish_paused_job_sync
        from cys_core.middleware import hitl_pause
        from cys_core.observability.metrics import metrics

        store = self.get_job_store()

        class _JobStoreHitlAdapter:
            def pause_for_hitl(self, pending: Any, preview: dict[str, Any]) -> None:
                store.pause_for_hitl(pending, preview)

            def list_pending_approvals(self) -> list[Any]:
                return store.list_pending_approvals()

        hitl_pause.configure(
            registry=_JobStoreHitlAdapter(),
            publish_paused=publish_paused_job_sync,
            on_pause_count=lambda count: metrics.refresh_hitl_pending(count),
        )

    def wire_tool_backend(self) -> None:
        from cys_core.infrastructure.tools.adapters.rag import rag_query_tool
        from cys_core.infrastructure.tools.adapters.siem import query_siem_readonly_search
        from cys_core.infrastructure.tools.audit import configure_tool_audit
        from cys_core.infrastructure.tools.gateway_factory import configure_tool_execution_gateway
        from cys_core.registry.tools import configure_tool_backend

        class _GatewayToolBackend:
            def query_siem(self, query: str, time_range: str = "24h") -> dict[str, Any]:
                return query_siem_readonly_search(query=query, time_range=time_range)

            def rag_query(self, query: str, persona: str = "soc", tenant: str = "default") -> dict[str, Any]:
                return rag_query_tool(query=query, persona=persona, tenant=tenant)

        configure_tool_backend(_GatewayToolBackend())
        configure_tool_audit(use_kafka=self.settings.use_kafka, settings=self.settings)
        configure_tool_execution_gateway(self.get_tool_execution_gateway())

    def wire_bus_reload(self) -> None:
        from cys_core.infrastructure.catalog.catalog_registry import register_bus_reload_callback
        from interfaces.worker.orchestrator import build_agent_bus

        register_bus_reload_callback(build_agent_bus)

    def wire_agent_definitions_loader(self) -> None:
        from bootstrap.agent_definitions_loader import get_default_agent_definitions_loader
        from bootstrap.otel_wiring import wire_otel
        from cys_core.application.ports.persistence_provider import configure_persistence_providers
        from cys_core.application.ports.trace_callbacks import configure_trace_callbacks
        from cys_core.observability.langfuse_client import configure_trace_backend_factory
        from cys_core.registry.agents import configure_agent_definitions_loader

        wire_otel()
        configure_persistence_providers(self.get_persistence_context, self.get_async_persistence_context)

        def _trace_callbacks():
            handler = self.get_trace_backend().get_callback_handler()
            return [handler] if handler is not None else []

        configure_trace_callbacks(_trace_callbacks)
        configure_trace_backend_factory(self.get_trace_backend)
        loader = get_default_agent_definitions_loader()
        configure_agent_definitions_loader(loader)

    def wire_catalog_ports(self) -> None:
        from cys_core.application.datasources.providers import configure_datasource_audit, configure_datasource_catalog
        from cys_core.application.plans_as_hints import configure_plan_hints
        from cys_core.application.persona_quality_hooks import configure_persona_quality
        from cys_core.application.reasoning.sgr_iron_metrics import configure_sgr_iron_metrics
        from cys_core.application.resource_source import configure_resource_source
        from cys_core.application.runs.budget_metrics import configure_budget_metrics
        from cys_core.application.skills.catalog import configure_skill_registry, configure_skills_agents_root
        from cys_core.application.tools.registry_provider import RegistryToolProvider, configure_default_tool_provider
        from cys_core.application.use_cases.extract_structured_output import configure_output_schema_catalog
        from cys_core.registry.discovery_tools import set_catalog_provider, set_persona_ranking_provider

        configure_resource_source(self.get_resource_source_port())
        configure_datasource_catalog(self.get_datasource_catalog_port())
        configure_datasource_audit(self.get_datasource_audit_port())
        configure_persona_quality(
            catalog=self.get_agent_catalog(),
            policy_port=self.get_profile_policy_port(),
            metrics_port=self.get_metrics_port(),
            mutation=self.get_catalog_mutation_service(),
        )
        configure_budget_metrics(self.get_metrics_port())
        configure_sgr_iron_metrics(self.get_metrics_port())
        configure_plan_hints(plan_catalog=self.get_plan_catalog(), agents_root=self.get_agents_root_port())
        configure_skill_registry(self.get_skill_registry_port())
        configure_skills_agents_root(self.get_agents_root_port())
        configure_output_schema_catalog(self.get_agent_catalog())
        configure_default_tool_provider(
            RegistryToolProvider(tool_registry=self.get_tool_registry_port()),
        )
        set_catalog_provider(self.get_agent_catalog())
        set_persona_ranking_provider(self.get_persona_ranking_port())

    def wire_runtime(self) -> None:
        from cys_core.runtime.agent import configure_runtime_memory_reader

        configure_runtime_memory_reader(self.get_memory_read_service())


_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is not None:
        return _container
    container = Container()
    _container = container
    container.wire_agent_definitions_loader()
    container.wire_catalog_ports()
    container.wire_runtime()
    container.wire_hitl_pause()
    container.wire_tool_backend()
    container.wire_bus_reload()
    container.wire_engagement_egress()
    _ensure_dev_catalog_seeded(container)
    return container


def _ensure_dev_catalog_seeded(container: Container) -> None:
    """Auto-seed Postgres catalog in dev when empty."""
    import structlog

    settings = container.settings
    if not settings.use_dynamic_catalog or settings.stage != "dev":
        return
    catalog = get_agent_catalog()
    try:
        if catalog.list_agents(enabled_only=False):
            reload_agent_registry()
            return
    except Exception:
        return
    try:
        from bootstrap.catalog_loader import load_profile_pack
        from cys_core.application.use_cases.seed_catalog import SeedCatalog
        from cys_core.infrastructure.catalog.tool_catalog_seed import load_tools_for_seed

        SeedCatalog(
            catalog,
            tool_catalog=container.get_tool_catalog(),
            seed_loaders=container.get_catalog_seed_loaders_port(),
            load_profile_pack=load_profile_pack,
            load_tools_for_seed=load_tools_for_seed,
            reload=container.reload_catalog,
            mutation=container.get_catalog_mutation_service(),
        ).execute()
        structlog.get_logger(__name__).info("dev_catalog_auto_seeded")
    except Exception as exc:
        structlog.get_logger(__name__).warning("dev_catalog_auto_seed_failed", error=str(exc))


def ensure_bus_router_wired() -> None:
    """Wire bus router after composition root is cached (avoids init recursion)."""
    get_container().wire_bus_router()


__all__ = [
    "DEFAULT_PROFILE_ID",
    "Container",
    "ensure_bus_router_wired",
    "get_agent_catalog",
    "get_breaker_config",
    "get_bus_policy",
    "get_container",
    "get_cost_per_1k_tokens",
    "get_escalation_paths",
    "get_hitl_threshold",
    "get_max_spawn_depth",
    "get_notify_control_severities",
    "get_profile_policy",
    "get_trust_floor",
]
