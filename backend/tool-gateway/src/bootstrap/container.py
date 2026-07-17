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
    from cys_core.application.ports.bus import AgentTransportConnector
    from cys_core.application.ports.job_queue import JobQueueConnector
    from cys_core.application.ports.memory import EpisodicMemoryStore


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
        # in api. See docs/MICROSERVICES_SPLIT_PLAN.md §0/§1.2/§18.
        self._reflexion_store = None
        self._tool_registry_port = None

    # ------------------------------------------------------------------
    # Engagement / event routing / bus orchestration
    # ------------------------------------------------------------------

    def bus_guard_config(self):
        return self._engagement.bus_guard_config()

    def get_engagement_bus_guard(self):
        return self._engagement.get_engagement_bus_guard()

    # get_event_router/get_route_event/get_dispatch_event delegating
    # wrappers removed along with their EngagementContainer implementations
    # — see docs/MICROSERVICES_SPLIT_PLAN.md §21.6.

    # get_worker_orchestrator/get_run_worker_job/get_agent_runtime/
    # get_meta_planner delegating wrappers removed along with their
    # EngagementContainer implementations — see
    # docs/MICROSERVICES_SPLIT_PLAN.md §21.6.

    def wire_engagement_egress(self) -> None:
        self._engagement.wire_engagement_egress()

    def get_engagement_state_store(self):
        return self._engagement.get_engagement_state_store()

    def get_engagement_egress(self):
        return self._engagement.get_engagement_egress()

    # get_orchestration_port delegating wrapper removed along with its
    # EngagementContainer implementation — see
    # docs/MICROSERVICES_SPLIT_PLAN.md §21.6.

    # get_bus_ingress_router/wire_bus_router/get_plan_investigation
    # delegating wrappers removed along with their EngagementContainer
    # implementations — see docs/MICROSERVICES_SPLIT_PLAN.md §21.6.

    # ------------------------------------------------------------------
    # Persistence / queue / transport / sandbox / memory
    # ------------------------------------------------------------------

    def get_job_queue(self, persona: str | None = None) -> JobQueueConnector:
        return self._persistence.get_job_queue(persona)

    def get_bus_transport(self) -> AgentTransportConnector:
        return self._persistence.get_bus_transport()

    # get_sandbox_connector (cys_core.infrastructure.sandbox — mints
    # short-lived MCP Tool Gateway credentials for a sandboxed agent run)
    # removed — only ever called by the deleted worker-job-pipeline cluster.
    # See docs/MICROSERVICES_SPLIT_PLAN.md §21.6.

    # get_persistence_context/get_async_persistence_context (worker's copy)
    # open the LangGraph checkpoint/store connector (cys_core.persistence) —
    # nothing in this package's execution path needs agent-thread
    # persistence. Removed along with the configure_persistence_providers(...)
    # call in wire_agent_definitions_loader() below that only ever passed
    # these two methods by reference (lazily, never actually invoked here).
    # See docs/MICROSERVICES_SPLIT_PLAN.md §21.6.

    # get_job_store delegating wrapper removed along with its
    # PersistenceContainer implementation — see
    # docs/MICROSERVICES_SPLIT_PLAN.md §21.6.

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

    # get_context_summarizer (cys_core.infrastructure.context.factory)
    # removed — only ever called by the deleted agent-run/context-building
    # cluster. See docs/MICROSERVICES_SPLIT_PLAN.md §21.6.

    def get_reflexion_store(self):
        if self._reflexion_store is not None:
            return self._reflexion_store
        from cys_core.infrastructure.reflexion.memory import get_reflexion_store

        self._reflexion_store = get_reflexion_store()
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
        # Worker's copy resolves this to cys_core.registry.tools.tool_registry
        # (the full LangChain agent tool catalog) — this package never has
        # that module. InvokeTool only ever uses this port as a soft,
        # gracefully-degrading fallback for JSON-schema hints
        # (fetch_tool_input_schema catches any exception and skips
        # pre-invoke validation) — never for execution (§21.5 removed that
        # fallback entirely). A registry with no entries produces exactly
        # that degrade-gracefully behavior. See
        # docs/MICROSERVICES_SPLIT_PLAN.md §21.6.
        if self._tool_registry_port is not None:
            return self._tool_registry_port

        class _EmptyToolRegistry:
            def get(self, name: str):
                raise KeyError(f"Unknown tool: {name}")

            def names(self, *, profile_id: str | None = None) -> list[str]:
                return []

            def resolve(self, names: list[str], profile_id: str = "cybersec-soc") -> list[Any]:
                return []

        self._tool_registry_port = _EmptyToolRegistry()
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

    # wire_hitl_pause (worker's copy, cys_core.middleware.hitl_pause) pauses
    # the in-process LangGraph agent run pending human approval — unrelated
    # to interfaces/gateways/tool/approval.py's own tool-call approval flow.
    # Removed, its call already dropped from get_container() below. See
    # docs/MICROSERVICES_SPLIT_PLAN.md §21.6.

    def wire_tool_backend(self) -> None:
        # configure_tool_backend(_GatewayToolBackend()) (worker's copy) wires
        # cys_core.registry.tools's module-level _tool_backend, read only by
        # that module's own query_siem_readonly/rag_query @tool wrappers —
        # the agent-facing LangChain tools, which live in worker only. This
        # package's own /invoke path reaches the same query_siem_readonly_search/
        # rag_query_tool functions directly via ADAPTERS, never through that
        # global. See docs/MICROSERVICES_SPLIT_PLAN.md §21.6.
        from cys_core.infrastructure.tools.audit import configure_tool_audit
        from cys_core.infrastructure.tools.gateway_factory import configure_tool_execution_gateway

        configure_tool_audit(use_kafka=self.settings.use_kafka, settings=self.settings)
        configure_tool_execution_gateway(self.get_tool_execution_gateway())
        # configure_manifest_lookup(get_manifest_port()) dropped — its read
        # side (get_manifest_lookup()) has zero callers anywhere in this
        # package, and cys_core.application.workers/__init__.py (needed to
        # reach tool_execution_tracker) eagerly imports WorkerAgentExecutor,
        # which pulls in cys_core.llm (langchain_core). Not this package's
        # concern. See docs/MICROSERVICES_SPLIT_PLAN.md §21.6.

    # wire_bus_reload (interfaces.worker.orchestrator.build_agent_bus)
    # removed — SecureAgentBus inter-agent messaging, not this package's
    # concern; its call already dropped from get_container() below.

    def wire_agent_definitions_loader(self) -> None:
        from bootstrap.agent_definitions_loader import get_default_agent_definitions_loader
        from bootstrap.otel_wiring import wire_otel
        from cys_core.application.ports.trace_callbacks import configure_trace_callbacks
        from cys_core.observability.langfuse_client import configure_trace_backend_factory
        from cys_core.registry.agents import configure_agent_definitions_loader

        wire_otel()

        def _trace_callbacks():
            handler = self.get_trace_backend().get_callback_handler()
            return [handler] if handler is not None else []

        configure_trace_callbacks(_trace_callbacks)
        configure_trace_backend_factory(self.get_trace_backend)
        loader = get_default_agent_definitions_loader()
        configure_agent_definitions_loader(loader)

    def wire_catalog_ports(self) -> None:
        # Trimmed for the standalone tool-gateway package (see
        # docs/MICROSERVICES_SPLIT_PLAN.md §21.6): the full version of this
        # method (worker's copy) also wires agent-catalog/persona-quality/
        # skill/budget-metrics/output-schema-catalog/default-tool-provider —
        # all agent-runtime/planning concerns InvokeTool's execution path
        # never touches. Kept here: configure_resource_source/
        # configure_datasource_catalog/configure_datasource_audit, the three
        # actually read by authorize_tool_datasource() in
        # InvokeTool._execute_inner(). Dropped configure_default_tool_provider
        # (RegistryToolProvider) entirely — it implemented ToolProviderPort,
        # already deleted from this package's ports/__init__.py as unused
        # (see §21.1) — and set_tool_lister_provider(list_tools) from
        # cys_core.registry.tools, the full LangChain tool catalog this
        # package intentionally never imports; search_tools() degrades to []
        # gracefully when this isn't configured.
        from cys_core.application.datasources.providers import configure_datasource_audit, configure_datasource_catalog
        from cys_core.application.resource_source import configure_resource_source

        configure_resource_source(self.get_resource_source_port())
        configure_datasource_catalog(self.get_datasource_catalog_port())
        configure_datasource_audit(self.get_datasource_audit_port())

    # wire_runtime (cys_core.runtime.agent.configure_runtime_memory_reader)
    # removed — the LangGraph agent loop, not this package's concern; its
    # call already dropped from get_container() below.


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
    # wire_runtime() (cys_core.runtime.agent — the LangGraph agent loop),
    # wire_bus_reload() (interfaces.worker.orchestrator — SecureAgentBus
    # inter-agent messaging), and wire_hitl_pause() (cys_core.middleware —
    # LangGraph agent-run pause/resume, unrelated to
    # interfaces/gateways/tool/approval.py's own tool-call approval flow)
    # are worker/agent-runtime-only; InvokeTool never touches any of them.
    # See docs/MICROSERVICES_SPLIT_PLAN.md §21.6.
    container.wire_tool_backend()
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


__all__ = [
    "DEFAULT_PROFILE_ID",
    "Container",
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
