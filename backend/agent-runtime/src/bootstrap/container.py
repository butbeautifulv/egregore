from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bootstrap.containers.auth_container import AuthContainer
from bootstrap.containers.catalog_container import CatalogContainer
from bootstrap.containers.engagement_container import EngagementContainer
from bootstrap.containers.observability_container import ObservabilityContainer
from bootstrap.containers.persistence_container import PersistenceContainer
from bootstrap.containers.policy_container import PolicyContainer
from bootstrap.containers.tools_container import ToolsContainer
from bootstrap.persona_budget_loader import load_persona_budgets
from bootstrap.settings import Settings
from cys_core.application.catalog_singletons import configure_catalog_singleton_rebind
from cys_core.application.policy_enforcement import PolicyEnforcementService
from cys_core.application.policy_resolver import ProfilePolicyResolver
from cys_core.application.runtime_config import configure_from_settings
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.policy.defaults import configure_persona_budgets
from cys_core.domain.workers.job_budget import configure_job_cost
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
from cys_core.infrastructure.config.infra_settings import (
    configure_docker_sandbox_settings,
    configure_egress_streaming_settings,
    configure_http_timeouts,
    configure_wayback_settings,
)


def get_settings() -> Settings:
    from bootstrap.settings import get_settings as _settings_get_settings

    return _settings_get_settings()

if TYPE_CHECKING:
    from cys_core.application.ports import PersistenceContext
    from cys_core.application.ports.bus import AgentTransportConnector
    from cys_core.application.ports.job_queue import JobQueueConnector
    from cys_core.application.ports.memory import EpisodicMemoryStore
    from cys_core.application.ports.sandbox import SandboxConnector


class Container:
    """Composition root for infrastructure connectors, catalog ports, and policy wiring.

    Construction logic is split across sub-containers by responsibility
    (see ``bootstrap/containers/``): ``CatalogContainer`` (catalog/registry
    ports), ``PersistenceContainer`` (queue/transport/sandbox/memory
    stores), ``EngagementContainer`` (event routing/dispatch, worker job
    pipeline, bus orchestration), ``ToolsContainer`` (tool chain policy and
    invocation), ``AuthContainer`` (authn/authz), ``ObservabilityContainer``
    (metrics/tracing/eval backends), and ``PolicyContainer`` (profile
    policy resolution, built eagerly). ``Container`` itself keeps every
    ``get_*()`` method that existed before this split — each one now
    delegates to the owning sub-container instead of constructing inline —
    so it remains the sole entry point (service-locator surface) used
    throughout the app.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings if settings is not None else get_settings()
        configure_from_settings(self.settings)
        configure_job_cost(self.settings.job_cost_per_1k_tokens_usd)
        configure_persona_budgets(load_persona_budgets(self.settings))
        self._wire_infra_settings(self.settings)
        self._wire_catalog_singleton_rebind()

        self._policy = PolicyContainer(self.settings)
        self._catalog = CatalogContainer(self)
        self._persistence = PersistenceContainer(self)
        self._engagement = EngagementContainer(self)
        self._tools = ToolsContainer(self)
        self._auth = AuthContainer(self)
        self._observability = ObservabilityContainer(self)
        # Worker-only, cached directly here rather than on the generic
        # PersistenceContainer/CatalogContainer — these back onto
        # cys_core.infrastructure.sandbox/cys_core.persistence/context.factory/
        # reflexion.memory/registry.tool_registry_adapter, none of which exist
        # in api. See docs/MSP_BACKLOG.md §0/§1.2/§18.
        self._context_summarizer = None
        self._reflexion_store = None
        self._tool_registry_port = None

    # ------------------------------------------------------------------
    # Engagement / event routing / bus orchestration
    # ------------------------------------------------------------------

    def bus_guard_config(self):
        return self._engagement.bus_guard_config()

    def get_engagement_bus_guard(self):
        return self._engagement.get_engagement_bus_guard()

    def get_event_router(self):
        return self._engagement.get_event_router()

    def get_route_event(self):
        return self._engagement.get_route_event()

    def get_dispatch_event(self):
        return self._engagement.get_dispatch_event()

    def get_worker_orchestrator(self, persona: str | None = None):
        return self._engagement.get_worker_orchestrator(persona)

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
        return self._engagement.get_run_worker_job(
            persona,
            runtime=runtime,
            registry=registry,
            bus=bus,
            sandbox=sandbox,
            transport=transport,
            queue=queue,
            sanitizer=sanitizer,
        )

    def get_agent_runtime(self):
        return self._engagement.get_agent_runtime()

    def get_meta_planner(self):
        return self._engagement.get_meta_planner()

    def wire_engagement_egress(self) -> None:
        self._engagement.wire_engagement_egress()

    def get_engagement_state_store(self):
        return self._engagement.get_engagement_state_store()

    def get_engagement_egress(self):
        return self._engagement.get_engagement_egress()

    def get_bus_ingress_router(self):
        return self._engagement.get_bus_ingress_router()

    def wire_bus_router(self) -> None:
        self._engagement.wire_bus_router()

    def get_orchestration_port(self):
        return self._engagement.get_orchestration_port()

    def get_plan_investigation(self):
        return self._engagement.get_plan_investigation()

    # ------------------------------------------------------------------
    # Persistence / queue / transport / sandbox / memory
    # ------------------------------------------------------------------

    def get_job_queue(self, persona: str | None = None) -> JobQueueConnector:
        return self._persistence.get_job_queue(persona)

    def get_bus_transport(self) -> AgentTransportConnector:
        return self._persistence.get_bus_transport()

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
        return self._persistence.get_job_store()

    def get_bus_dedup_store(self):
        return self._persistence.get_bus_dedup_store()

    def get_episodic_memory_store(self) -> EpisodicMemoryStore:
        return self._persistence.get_episodic_memory_store()

    def get_memory_read_service(self):
        return self._persistence.get_memory_read_service()

    def get_memory_write_service(self):
        return self._persistence.get_memory_write_service()

    def get_attachment_store(self):
        return self._persistence.get_attachment_store()

    def get_workspace_store(self):
        return self._persistence.get_workspace_store()

    def get_context_summarizer(self):
        if self._context_summarizer is not None:
            return self._context_summarizer
        from cys_core.infrastructure.context.factory import get_context_summarizer

        self._context_summarizer = get_context_summarizer()
        return self._context_summarizer

    def get_reflexion_store(self):
        if self._reflexion_store is not None:
            return self._reflexion_store
        # Adapts onto the same episodic-memory backend (Postgres, with connect-with-retry
        # and memory fallback already wired) instead of the module's own bare in-memory
        # default — reflexion lessons used to be lost on every process restart with no
        # durable path at all. docs/MSP_BACKLOG.md §9/§38.
        from cys_core.infrastructure.reflexion.memory import EpisodicReflexionStore

        self._reflexion_store = EpisodicReflexionStore(self.get_episodic_memory_store())
        return self._reflexion_store

    # ------------------------------------------------------------------
    # Catalog / registry ports
    # ------------------------------------------------------------------

    def get_product_pack_port(self):
        return self._catalog.get_product_pack_port()

    def get_catalog_seed_loaders_port(self):
        return self._catalog.get_catalog_seed_loaders_port()

    def get_policy_defaults_port(self):
        return self._catalog.get_policy_defaults_port()

    def get_application_settings_port(self):
        return self._catalog.get_application_settings_port()

    def get_catalog_version(self) -> int:
        return self._catalog.get_catalog_version()

    def get_seed_catalog(self):
        return self._catalog.get_seed_catalog()

    def get_agent_catalog(self):
        return self._catalog.get_agent_catalog()

    def get_skill_catalog(self):
        return self._catalog.get_skill_catalog()

    def get_plan_catalog(self):
        return self._catalog.get_plan_catalog()

    def get_mcp_catalog(self):
        return self._catalog.get_mcp_catalog()

    def get_tool_catalog(self):
        return self._catalog.get_tool_catalog()

    def get_catalog_write_gate(self):
        return self._catalog.get_catalog_write_gate()

    def get_catalog_audit(self):
        return self._catalog.get_catalog_audit()

    def get_agent_registry_port(self):
        return self._catalog.get_agent_registry_port()

    def get_schema_registry_port(self):
        return self._catalog.get_schema_registry_port()

    def get_tool_registry_port(self):
        if self._tool_registry_port is not None:
            return self._tool_registry_port
        from cys_core.infrastructure.registry.tool_registry_adapter import build_tool_registry_port

        self._tool_registry_port = build_tool_registry_port()
        return self._tool_registry_port

    def get_persona_ranking_port(self):
        return self._catalog.get_persona_ranking_port()

    def get_skill_registry_port(self):
        return self._catalog.get_skill_registry_port()

    def get_resource_source_port(self):
        return self._catalog.get_resource_source_port()

    def get_agents_root_port(self):
        return self._catalog.get_agents_root_port()

    def get_datasource_catalog_port(self):
        return self._catalog.get_datasource_catalog_port()

    def get_datasource_audit_port(self):
        return self._catalog.get_datasource_audit_port()

    def get_policy_merge_port(self):
        return self._catalog.get_policy_merge_port()

    def get_catalog_mutation_service(self):
        return self._catalog.get_catalog_mutation_service()

    def reload_catalog(self) -> None:
        self._catalog.reload_catalog()

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def get_tool_chain_policy(self):
        return self._tools.get_tool_chain_policy()

    def get_invoke_tool(self):
        return self._tools.get_invoke_tool()

    def get_tool_execution_gateway(self):
        return self._tools.get_tool_execution_gateway()

    # ------------------------------------------------------------------
    # Auth / authz
    # ------------------------------------------------------------------

    def get_token_verifier(self):
        return self._auth.get_token_verifier()

    def get_authz_service(self):
        return self._auth.get_authz_service()

    def get_authz_port(self):
        return self._auth.get_authz_port()

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics_port(self):
        return self._observability.get_metrics_port()

    def get_correlation_id_port(self):
        return self._observability.get_correlation_id_port()

    def get_worker_tracing_port(self):
        return self._observability.get_worker_tracing_port()

    def get_application_tracing_port(self):
        return self._observability.get_application_tracing_port()

    def get_trace_flush_port(self):
        return self._observability.get_trace_flush_port()

    def get_trace_backend(self):
        return self._observability.get_trace_backend()

    def get_prompt_backend(self):
        return self._observability.get_prompt_backend()

    def get_judge_backend(self):
        return self._observability.get_judge_backend()

    def get_eval_backend(self):
        return self._observability.get_eval_backend()

    def get_prompt_resolver(self):
        return self._observability.get_prompt_resolver()

    # ------------------------------------------------------------------
    # Policy (built eagerly in __init__)
    # ------------------------------------------------------------------

    def get_profile_policy_port(self) -> ProfilePolicyLoader:
        return self._policy.get_profile_policy_port()

    def get_run_state_store(self):
        from cys_core.infrastructure.runs.factory import get_run_state_store

        return get_run_state_store()

    def get_build_job_trace_metadata(self):
        from cys_core.observability.trace_attributes import build_job_trace_metadata

        return build_job_trace_metadata

    def get_policy_resolver(self) -> ProfilePolicyResolver:
        return self._policy.get_policy_resolver()

    def get_policy_enforcement(self) -> PolicyEnforcementService:
        return self._policy.get_policy_enforcement()

    @staticmethod
    def _wire_infra_settings(settings: Settings) -> None:
        configure_http_timeouts(
            connect_s=settings.http_connect_timeout_s,
            read_s=settings.http_read_timeout_s,
        )
        configure_docker_sandbox_settings(
            probe_timeout_s=settings.docker_probe_timeout_s,
            kill_timeout_s=settings.docker_kill_timeout_s,
        )
        configure_egress_streaming_settings(
            output_preview_max=settings.egress_output_preview_max,
            batch_seconds=settings.egress_batch_seconds,
        )
        configure_wayback_settings(api_timeout_s=settings.wayback_api_timeout_s)

    @staticmethod
    def _wire_catalog_singleton_rebind() -> None:
        def _rebind(prev_use_postgres: bool, new_use_postgres: bool) -> None:
            if prev_use_postgres == new_use_postgres:
                return
            from cys_core.infrastructure.catalog.catalog_singletons import CatalogSingletons

            CatalogSingletons.reset(
                "agent_catalog",
                "tool_catalog",
                "skill_catalog",
                "plan_catalog",
                "mcp_catalog",
                "catalog_audit",
                "catalog_write_gate",
            )

        configure_catalog_singleton_rebind(_rebind)

    # ------------------------------------------------------------------
    # Cross-cutting bootstrap wiring (touches multiple sub-containers)
    # ------------------------------------------------------------------

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

        def _publish_paused(record: dict[str, Any]) -> None:
            publish_paused_job_sync(record)

        hitl_pause.configure(
            registry=_JobStoreHitlAdapter(),
            publish_paused=_publish_paused,
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
        from cys_core.application.runs.tool_coercion import configure_manifest_lookup
        from cys_core.application.workers.tool_execution_tracker import get_manifest_port

        configure_manifest_lookup(get_manifest_port())

    def wire_bus_reload(self) -> None:
        from cys_core.infrastructure.catalog.catalog_registry import register_bus_reload_callback
        from interfaces.worker.orchestrator import build_agent_bus

        def _reload_bus(_registry: object) -> None:
            build_agent_bus(signing_key=self.settings.bus_signing_key_bytes)

        register_bus_reload_callback(_reload_bus)

    def wire_agent_definitions_loader(self) -> None:
        from bootstrap.agent_definitions_loader import get_default_agent_definitions_loader
        from bootstrap.otel_wiring import wire_otel
        from cys_core.application.ports.persistence_provider import configure_persistence_providers
        from cys_core.application.ports.profile_policy_provider import configure_profile_policy_provider
        from cys_core.application.ports.trace_callbacks import configure_trace_callbacks
        from cys_core.observability.langfuse_client import configure_trace_backend_factory
        from cys_core.registry.agents import configure_agent_definitions_loader

        wire_otel()
        configure_persistence_providers(self.get_persistence_context, self.get_async_persistence_context)
        configure_profile_policy_provider(self.get_profile_policy_port)

        def _trace_callbacks():
            handler = self.get_trace_backend().get_callback_handler()
            return [handler] if handler is not None else []

        configure_trace_callbacks(_trace_callbacks)
        configure_trace_backend_factory(self.get_trace_backend)
        loader = get_default_agent_definitions_loader()
        configure_agent_definitions_loader(loader)

    def wire_catalog_ports(self) -> None:
        from cys_core.application.datasources.providers import configure_datasource_audit, configure_datasource_catalog
        from cys_core.application.persona_quality_hooks import configure_persona_quality
        from cys_core.application.plans_as_hints import configure_plan_hints
        from cys_core.application.reasoning.sgr_iron_metrics import configure_sgr_iron_metrics
        from cys_core.application.resource_source import configure_resource_source
        from cys_core.application.runs.budget_metrics import configure_budget_metrics
        from cys_core.application.skills.catalog import configure_skill_registry, configure_skills_agents_root
        from cys_core.application.tools.registry_provider import RegistryToolProvider, configure_default_tool_provider
        from cys_core.application.use_cases.extract_structured_output import configure_output_schema_catalog
        from cys_core.registry.discovery_tools import (
            set_catalog_provider,
            set_persona_ranking_provider,
            set_tool_lister_provider,
        )
        from cys_core.registry.product_context import (
            set_catalog_provider as set_product_context_catalog_provider,
        )
        from cys_core.registry.tools import list_tools

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
        set_product_context_catalog_provider(self.get_agent_catalog())
        set_tool_lister_provider(list_tools)

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
    _ensure_dev_catalog_seeded(container)
    _ensure_tool_catalog_seeded(container)
    container.wire_catalog_ports()
    container.wire_runtime()
    container.wire_hitl_pause()
    container.wire_tool_backend()
    container.wire_bus_reload()
    container.wire_engagement_egress()
    return container


def _ensure_tool_catalog_seeded(container: Container) -> None:
    """Seed tool_catalog when Postgres table is empty (prod and dev)."""
    import structlog

    settings = container.settings
    if not settings.use_dynamic_catalog or settings.use_memory_fallback:
        return
    tool_catalog = container.get_tool_catalog()
    try:
        if tool_catalog.list_tools(enabled_only=False):
            return
    except Exception:
        return
    try:
        from cys_core.infrastructure.catalog.tool_catalog_seed import load_tools_for_seed

        tools = load_tools_for_seed()
        tool_catalog.seed(tools)
        container.reload_catalog()
        structlog.get_logger(__name__).info("tool_catalog_auto_seeded", count=len(tools))
    except Exception as exc:
        structlog.get_logger(__name__).warning("tool_catalog_auto_seed_failed", error=str(exc))


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
