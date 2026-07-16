from functools import lru_cache
from pathlib import Path
from typing import Any, Self

from pydantic import Field, SecretStr, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_STAGES = frozenset({"dev", "test", "staging", "prod"})
_ALLOWED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_ALLOWED_LOG_FORMATS = frozenset({"json", "text"})
_ALLOWED_CONTROL_MODES = frozenset({"inprocess", "daemon"})
_ALLOWED_SIEM_ADAPTERS = frozenset({"mock", "http"})
_ALLOWED_SGR_MODES = frozenset({"off", "soft", "iron", "sgr_hybrid", "sgr_iron", "hybrid"})
_ALLOWED_STORE_CONNECTORS = frozenset({"auto", "memory", "postgres", "redis"})
_ALLOWED_AUTHZ_MODES = frozenset({"off", "shadow", "enforce"})
_DEFAULT_REDIS_PASSWORD = "password"
_DEFAULT_POSTGRES_PASSWORD = "password"
_DEFAULT_BUS_SIGNING_KEY = "cys-agi-bus-key"


def _settings_env_files() -> tuple[str, ...]:
    """Load the running service's own .env (via CWD — `uv run egregore ...`
    is always invoked with CWD set to that service's own directory), then
    repo-root .env, then deploy/.secrets.

    Does not look for "this module's own nearest pyproject.toml" the way it
    used to — `bootstrap.settings` now lives in the shared `contracts`
    package, installed into multiple sibling services (backend/shared,
    backend/api, backend/worker), so `Path(__file__)` here always points
    into `contracts/`, never into whichever service is actually running.
    CWD already covers the "this service's own .env" case correctly.
    """
    from bootstrap.paths import find_repo_root

    files: list[str] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        if path.is_file():
            resolved = str(path.resolve())
            if resolved not in seen:
                seen.add(resolved)
                files.append(resolved)

    _add(Path.cwd() / ".env")

    try:
        repo_root = find_repo_root(Path(__file__).resolve().parent)
    except RuntimeError:
        repo_root = None

    if repo_root is not None:
        _add(repo_root / ".env")
        _add(repo_root / "deploy" / ".secrets" / "egregore-local.env")

    if not files:
        files.append(".env")
    return tuple(files)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_settings_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    ai_apikey: str = Field(default="", validation_alias="AI_APIKEY")

    llm_provider: str = Field(default="litellm", validation_alias="LLM_PROVIDER")
    llm_model: str = Field(default="anthropic/claude-sonnet-4", validation_alias="LLM_MODEL")
    llm_base_url: str | None = Field(default=None, validation_alias="LLM_BASE_URL")
    llm_temperature: float = Field(default=0.1, validation_alias="LLM_TEMPERATURE")
    llm_request_timeout: float = Field(
        default=120.0,
        validation_alias="LLM_REQUEST_TIMEOUT",
        description="LiteLLM request timeout in seconds (fail-fast when vLLM is down).",
    )
    worker_job_timeout: float = Field(
        default=180.0,
        validation_alias="WORKER_JOB_TIMEOUT",
        description="Hard wall-clock cap per worker job (sandbox + LLM + bus).",
    )
    worker_job_timeout_intel: float = Field(
        default=0.0,
        validation_alias="WORKER_JOB_TIMEOUT_INTEL",
        description="Optional override for intel persona jobs (0 = use WORKER_JOB_TIMEOUT).",
    )
    worker_job_timeout_synth: float = Field(
        default=0.0,
        validation_alias="WORKER_JOB_TIMEOUT_SYNTH",
        description="Optional override for synthesis phase jobs (0 = use WORKER_JOB_TIMEOUT).",
    )
    llm_thinking_token_budget: int = Field(
        default=0,
        validation_alias="LLM_THINKING_TOKEN_BUDGET",
        description=(
            "Sent as extra_body.thinking_token_budget on every LiteLLM call (0 = unset, "
            "no limit). Requires the vLLM server to have --reasoning-config enabled in "
            "addition to --reasoning-parser, otherwise vLLM rejects the request — this "
            "setting alone does not enable server-side enforcement."
        ),
    )
    engagement_async_planning: bool = Field(
        default=True,
        validation_alias="ENGAGEMENT_ASYNC_PLANNING",
        description="Defer meta-LLM engagement planning to background (API returns 202).",
    )
    coordinator_llm_narrative: bool = Field(
        default=False,
        validation_alias="COORDINATOR_LLM_NARRATIVE",
        description="Use LLM coordinator narrator (worker/control pod only).",
    )
    coordinator_chat_narrative: bool = Field(
        default=False,
        validation_alias="COORDINATOR_CHAT_NARRATIVE",
        description="Publish coordinator summaries into operator chat (default: progress events only).",
    )
    egregore_sandbox_v2: bool = Field(
        default=False,
        validation_alias="EGREGORE_SANDBOX_V2",
        description="Use Docker/Kata sandbox v2 workload isolation.",
    )
    planner_fallback_personas: str = Field(
        default="consultant",
        validation_alias="PLANNER_FALLBACK_PERSONAS",
        description="Comma-separated worker personas when LLM planner fails or returns unparseable JSON.",
    )
    max_planner_personas: int = Field(
        default=6,
        validation_alias="MAX_PLANNER_PERSONAS",
        description="Maximum specialist personas in a meta-LLM engagement plan.",
    )
    planner_default_execution_mode: str = Field(
        default="parallel",
        validation_alias="PLANNER_DEFAULT_EXECUTION_MODE",
        description="Default execution mode for multi-persona plans: parallel or staged.",
    )

    stage: str = Field(default="dev", validation_alias="STAGE")

    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_password: SecretStr = Field(
        default=SecretStr(_DEFAULT_REDIS_PASSWORD),
        validation_alias="REDIS_PASSWORD",
    )
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")

    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(
        default=SecretStr(_DEFAULT_POSTGRES_PASSWORD),
        validation_alias="POSTGRES_PASSWORD",
    )
    postgres_db: str = Field(default="egregore", validation_alias="POSTGRES_DB")

    langfuse_public_key: str = Field(default="", validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_api_key: str = Field(
        default="",
        validation_alias="LANGFUSE_API_KEY",
        description="Deprecated: use LANGFUSE_PUBLIC_KEY; kept for one-release backward compatibility",
    )
    langfuse_host: str = Field(default="http://localhost:3001", validation_alias="LANGFUSE_HOST")
    langfuse_base_url: str = Field(
        default="",
        validation_alias="LANGFUSE_BASE_URL",
        description="Alias for LANGFUSE_HOST (Langfuse SDK / skills convention)",
    )

    otel_enabled: bool = Field(default=False, validation_alias="OTEL_ENABLED")
    otel_exporter_endpoint: str = Field(
        default="http://localhost:4317",
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    otel_service_name: str = Field(default="", validation_alias="OTEL_SERVICE_NAME")

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default="json", validation_alias="LOG_FORMAT")

    otel_resource_attributes: str = Field(default="", validation_alias="OTEL_RESOURCE_ATTRIBUTES")
    otel_traces_sampler: str = Field(
        default="parentbased_always_on",
        validation_alias="OTEL_TRACES_SAMPLER",
    )
    otel_traces_sampler_arg: float = Field(default=1.0, validation_alias="OTEL_TRACES_SAMPLER_ARG")

    hitl_auto_approve_threshold: str = Field(default="low", validation_alias="HITL_AUTO_APPROVE_THRESHOLD")
    max_tool_calls_per_minute: int = Field(default=30, validation_alias="MAX_TOOL_CALLS_PER_MINUTE")
    trust_score_threshold: float = Field(
        default=0.5,
        validation_alias="TRUST_SCORE_THRESHOLD",
        description="Deprecated: use ProfilePack.policy.trust_floor per profile instead.",
    )
    use_memory_fallback: bool = Field(default=False, validation_alias="USE_MEMORY_FALLBACK")
    persistence_connector: str = Field(default="auto", validation_alias="PERSISTENCE_CONNECTOR")
    job_store_connector: str = Field(default="auto", validation_alias="JOB_STORE_CONNECTOR")
    engagement_store_connector: str = Field(default="auto", validation_alias="ENGAGEMENT_STORE_CONNECTOR")
    workspace_store_connector: str = Field(default="auto", validation_alias="WORKSPACE_STORE_CONNECTOR")
    bus_signing_key: SecretStr = Field(
        default=SecretStr(_DEFAULT_BUS_SIGNING_KEY),
        validation_alias="BUS_SIGNING_KEY",
    )
    siem_adapter: str = Field(default="mock", validation_alias="SIEM_ADAPTER")
    siem_base_url: str = Field(default="", validation_alias="SIEM_BASE_URL")
    use_real_embeddings: bool = Field(default=False, validation_alias="USE_REAL_EMBEDDINGS")
    agents_root: str = Field(default="agents", validation_alias="AGENTS_ROOT")
    use_dynamic_catalog: bool = Field(default=True, validation_alias="USE_DYNAMIC_CATALOG")
    obs_prompt_backend: str = Field(default="filesystem", validation_alias="OBS_PROMPT_BACKEND")
    obs_trace_backend: str = Field(default="langfuse", validation_alias="OBS_TRACE_BACKEND")
    obs_judge_backend: str = Field(default="noop", validation_alias="OBS_JUDGE_BACKEND")
    obs_eval_backend: str = Field(default="noop", validation_alias="OBS_EVAL_BACKEND")
    use_conductor_for_events: bool = Field(default=False, validation_alias="USE_CONDUCTOR_FOR_EVENTS")
    max_spawn_depth: int = Field(default=5, validation_alias="MAX_SPAWN_DEPTH")
    egregore_json_tool_call_fallback: bool = Field(
        default=True,
        validation_alias="EGREGORE_JSON_TOOL_CALL_FALLBACK",
    )
    egregore_one_tool_per_turn: bool = Field(
        default=True,
        validation_alias="EGREGORE_ONE_TOOL_PER_TURN",
        description="Limit agents to one tool call per model turn.",
    )
    egregore_strict_plan: bool = Field(default=False, validation_alias="EGREGORE_STRICT_PLAN")
    stream_agent_output: bool = Field(default=False, validation_alias="STREAM_AGENT_OUTPUT")
    stream_agent_tools: bool = Field(default=True, validation_alias="STREAM_AGENT_TOOLS")
    stream_agent_token_streaming: bool = Field(
        default=False,
        validation_alias="STREAM_AGENT_TOKEN_STREAMING",
    )
    keep_tool_results: int = Field(default=3, validation_alias="KEEP_TOOL_RESULTS")
    search_judge_llm: bool = Field(default=False, validation_alias="SEARCH_JUDGE_LLM")
    self_consistency_n: int = Field(default=0, validation_alias="SELF_CONSISTENCY_N")
    self_refine_max: int = Field(default=0, validation_alias="SELF_REFINE_MAX")
    browser_enabled: bool = Field(default=False, validation_alias="BROWSER_ENABLED")
    perplexity_api_key: str = Field(default="", validation_alias="PERPLEXITY_API_KEY")
    jina_api_key: str = Field(default="", validation_alias="JINA_API_KEY")
    delegate_budget_fraction: float = Field(default=0.35, validation_alias="DELEGATE_BUDGET_FRACTION")
    trace_critic_enabled: bool = Field(default=True, validation_alias="TRACE_CRITIC_ENABLED")
    trace_critic_threshold: float = Field(default=0.55, validation_alias="TRACE_CRITIC_THRESHOLD")
    trace_critic_every_n_steps: int = Field(default=3, validation_alias="TRACE_CRITIC_EVERY_N_STEPS")
    context_summary_max_messages: int = Field(default=40, validation_alias="CONTEXT_SUMMARY_MAX_MESSAGES")
    task_hints_enabled: bool = Field(default=True, validation_alias="TASK_HINTS_ENABLED")
    web_search_provider: str = Field(default="duckduckgo", validation_alias="WEB_SEARCH_PROVIDER")
    serper_api_key: str = Field(default="", validation_alias="SERPER_API_KEY")
    run_attachments_dir: str = Field(default="/tmp/egregore-attachments", validation_alias="RUN_ATTACHMENTS_DIR")
    context_summary_enabled: bool = Field(default=True, validation_alias="CONTEXT_SUMMARY_ENABLED")
    trace_critic_rerun_max: int = Field(default=2, validation_alias="TRACE_CRITIC_RERUN_MAX")
    trace_critic_hitl_on_exhausted: bool = Field(
        default=True,
        validation_alias="TRACE_CRITIC_HITL_ON_EXHAUSTED",
    )
    reasoning_model: str = Field(default="", validation_alias="REASONING_MODEL")
    reasoning_temperature: float = Field(default=0.0, validation_alias="REASONING_TEMPERATURE")
    trace_critic_use_reasoning: bool = Field(default=False, validation_alias="TRACE_CRITIC_USE_REASONING")
    use_sgr_reasoning: bool = Field(default=True, validation_alias="USE_SGR_REASONING")
    sgr_default_mode: str = Field(default="off", validation_alias="SGR_DEFAULT_MODE")
    sgr_iron_max_retries: int = Field(default=3, validation_alias="SGR_IRON_MAX_RETRIES")
    e2b_api_key: str = Field(default="", validation_alias="E2B_API_KEY")
    python_sandbox_timeout: float = Field(default=30.0, validation_alias="PYTHON_SANDBOX_TIMEOUT")
    python_sandbox_image: str = Field(
        default="python:3.12-slim",
        validation_alias="PYTHON_SANDBOX_IMAGE",
        description="Image for the local Docker sandbox fallback when E2B is not configured "
        "(offline deployments must bundle/import this image — see k3s-offline-bundle-*.sh).",
    )

    kafka_bootstrap_servers: str = Field(
        default="localhost:19092",
        validation_alias="KAFKA_BOOTSTRAP_SERVERS",
    )
    use_kafka: bool = Field(default=False, validation_alias="USE_KAFKA")
    strict_redis_queue: bool = Field(default=False, validation_alias="STRICT_REDIS_QUEUE")
    bus_max_jobs_per_engagement: int = Field(default=20, validation_alias="BUS_MAX_JOBS_PER_ENGAGEMENT")
    bus_max_total_jobs_window: int = Field(default=50, validation_alias="BUS_MAX_TOTAL_JOBS_WINDOW")
    bus_dedup_trip_threshold: int = Field(default=5, validation_alias="BUS_DEDUP_TRIP_THRESHOLD")
    bus_pingpong_trip_threshold: int = Field(default=3, validation_alias="BUS_PINGPONG_TRIP_THRESHOLD")
    bus_noop_churn_threshold: int = Field(default=10, validation_alias="BUS_NOOP_CHURN_THRESHOLD")
    bus_guard_window_seconds: int = Field(default=600, validation_alias="BUS_GUARD_WINDOW_SECONDS")
    bus_max_revisions_per_persona: int = Field(
        default=1,
        validation_alias="BUS_MAX_REVISIONS_PER_PERSONA",
        description="Max critic revision bus jobs per persona per engagement window.",
    )
    follow_up_enabled: bool = Field(default=True, validation_alias="EGREGORE_FOLLOW_UP_ENABLED")
    max_follow_ups_per_engagement: int = Field(
        default=10,
        validation_alias="EGREGORE_MAX_FOLLOW_UPS",
    )
    max_follow_up_spawns: int = Field(
        default=2,
        validation_alias="EGREGORE_MAX_FOLLOW_UP_SPAWNS",
    )
    follow_up_plan_enabled: bool = Field(
        default=True,
        validation_alias="EGREGORE_FOLLOW_UP_PLAN_ENABLED",
    )
    max_follow_up_plans_per_engagement: int = Field(
        default=3,
        validation_alias="EGREGORE_MAX_FOLLOW_UP_PLANS",
    )
    planner_timeout_seconds: int = Field(
        default=120,
        validation_alias="PLANNER_TIMEOUT_SECONDS",
        description="Fallback staged plan when async meta-LLM planner stays in planning.",
    )
    budget_use_api_usage: bool = Field(default=True, validation_alias="BUDGET_USE_API_USAGE")

    tool_gateway_url: str = Field(
        default="http://localhost:8092",
        validation_alias="TOOL_GATEWAY_URL",
        description="egregore MCP Tool Gateway (avoid :8090 — Veil Graph API).",
    )
    use_tool_gateway: bool = Field(default=False, validation_alias="USE_TOOL_GATEWAY")

    veil_mcp_url: str = Field(
        default="http://localhost:8091/mcp",
        validation_alias="VEIL_MCP_URL",
    )
    veil_mcp_enabled: bool = Field(default=True, validation_alias="VEIL_MCP_ENABLED")
    veil_mcp_timeout: float = Field(default=30.0, validation_alias="VEIL_MCP_TIMEOUT")

    siem_mcp_url: str = Field(
        default="http://localhost:8094/mcp",
        validation_alias="SIEM_MCP_URL",
    )
    siem_mcp_enabled: bool = Field(default=False, validation_alias="SIEM_MCP_ENABLED")
    siem_mcp_timeout: float = Field(default=180.0, validation_alias="SIEM_MCP_TIMEOUT")

    nessus_mcp_url: str = Field(
        default="http://localhost:8095/mcp",
        validation_alias="NESSUS_MCP_URL",
    )
    nessus_mcp_enabled: bool = Field(default=False, validation_alias="NESSUS_MCP_ENABLED")
    nessus_mcp_timeout: float = Field(default=180.0, validation_alias="NESSUS_MCP_TIMEOUT")

    veneno_mcp_url: str = Field(
        default="http://localhost:8093/mcp",
        validation_alias="VENENO_MCP_URL",
    )
    veneno_mcp_enabled: bool = Field(default=False, validation_alias="VENENO_MCP_ENABLED")
    veneno_mcp_timeout: float = Field(default=60.0, validation_alias="VENENO_MCP_TIMEOUT")

    job_cost_per_1k_tokens_usd: float = Field(
        default=0.003,
        validation_alias="JOB_COST_PER_1K_TOKENS_USD",
    )
    max_high_risk_tool_chain_depth: int = Field(
        default=3,
        validation_alias="MAX_HIGH_RISK_TOOL_CHAIN_DEPTH",
    )
    default_job_recursion_limit: int = Field(
        default=25,
        validation_alias="DEFAULT_JOB_RECURSION_LIMIT",
    )
    triage_recursion_limit: int = Field(
        default=22,
        validation_alias="TRIAGE_RECURSION_LIMIT",
        description="Lower LangGraph recursion cap for soc/intel triage personas.",
    )

    sandbox_connector: str = Field(default="local", validation_alias="SANDBOX_CONNECTOR")
    k8s_namespace: str = Field(default="cys-agi", validation_alias="K8S_NAMESPACE")
    k8s_worker_image: str = Field(
        default="cys-agi-worker:latest",
        validation_alias="K8S_WORKER_IMAGE",
    )
    docker_worker_image: str = Field(
        default="egregore-worker:latest",
        validation_alias="DOCKER_WORKER_IMAGE",
        description="Image DockerExecutionBackend runs via `docker run` for dev/CI "
        "job execution without a real Kubernetes cluster.",
    )
    docker_network: str = Field(
        default="",
        validation_alias="DOCKER_NETWORK",
        description="Docker network the sandboxed job container joins (e.g. the "
        "docker-compose project network, so it can reach postgres/redis by service "
        "name). Empty uses the docker daemon's default bridge — same as today.",
    )
    docker_env_file: str = Field(
        default="",
        validation_alias="DOCKER_ENV_FILE",
        description="Path to an env file (e.g. deploy/.secrets/egregore-local.env) "
        "passed to the sandboxed job container via `docker run --env-file`. A "
        "`docker run` child does not inherit the parent process's environment the "
        "way SubprocessExecutionBackend's plain subprocess does, so without this "
        "the container has no DEEPSEEK_API_KEY/POSTGRES_HOST/etc.",
    )
    k8s_sandbox_ttl_seconds: float = Field(
        default=600.0,
        validation_alias="K8S_SANDBOX_TTL_SECONDS",
        description="Hard cap (Job activeDeadlineSeconds) forcing kubelet to kill the "
        "sandbox pod if the agent hangs, and the TTL used for the sandbox's short-lived "
        "credential (sandbox_tokens.mint_sandbox_token).",
    )
    k8s_sandbox_ready_timeout_s: float = Field(
        default=30.0,
        validation_alias="K8S_SANDBOX_READY_TIMEOUT_S",
        description="Max time to wait for the sandbox Job's pod to be admitted/running "
        "before create() fails closed instead of handing back credentials for a sandbox "
        "that never actually started.",
    )
    k8s_sandbox_credentials_only: bool = Field(
        default=False,
        validation_alias="K8S_SANDBOX_CREDENTIALS_ONLY",
        description="When true, K8sSandboxConnector.create()/acreate() skip Job creation "
        "entirely and just mint+return credentials — set by K8sExecutionBackend in the "
        "pod's own env, so RunWorkerJob.execute() running inside a pod that backend "
        "already created doesn't spawn a second, parasitic Job for the same run_id "
        "(Discovery F, docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md).",
    )
    k8s_runtime_class: str | None = Field(
        default=None,
        validation_alias="K8S_RUNTIME_CLASS",
        description="RuntimeClass name (e.g. 'gvisor') set on worker Job pods when "
        "present — requires the containerd shim + RuntimeClass CR already installed "
        "on the cluster (Phase 4.1, infra-only, not this repo). Unset means no "
        "runtimeClassName field at all, i.e. today's runc behavior, unchanged.",
    )

    qdrant_url: str = Field(default="http://localhost:6333", validation_alias="QDRANT_URL")
    use_qdrant: bool = Field(default=False, validation_alias="USE_QDRANT")
    rag_max_chunks: int = Field(default=5, validation_alias="RAG_MAX_CHUNKS")

    status_store_connector: str = Field(default="auto", validation_alias="STATUS_STORE_CONNECTOR")
    control_mode: str = Field(default="inprocess", validation_alias="CONTROL_MODE")
    worker_idle_timeout: float = Field(
        default=0.0,
        validation_alias="WORKER_IDLE_TIMEOUT",
        description="Worker daemon idle exit (seconds). 0 = run until stopped.",
    )
    worker_replicas: int = Field(
        default=2,
        validation_alias="WORKER_REPLICAS",
        description="Number of worker daemon processes in dev supervisor / docker scale.",
    )

    auth_enabled: bool = Field(default=False, validation_alias="AUTH_ENABLED")
    rbac_enabled: bool = Field(default=False, validation_alias="RBAC_ENABLED")
    authz_mode: str = Field(default="off", validation_alias="AUTHZ_MODE")
    allow_legacy_tenant_tokens: bool = Field(
        default=False,
        validation_alias="ALLOW_LEGACY_TENANT_TOKENS",
        description="Whether require_tenant_match() trusts the requested tenant_id when the "
        "JWT lacks an organization_id claim (docs/MICROSERVICES_SPLIT_PLAN.md §11.3 — this used "
        "to be unconditional 'legacy token' backward-compat behavior; now it's opt-in). Default "
        "False is a behavior change from before this flag existed — a missing organization_id "
        "claim now rejects the request instead of silently trusting the caller.",
    )
    allow_insecure_prod_authz: bool = Field(
        default=False,
        validation_alias="ALLOW_INSECURE_PROD_AUTHZ",
        description="Explicit, temporary override to let STAGE=prod start with "
        "AUTH_ENABLED=0/RBAC_ENABLED=0/AUTHZ_MODE!=enforce (docs/MICROSERVICES_SPLIT_PLAN.md "
        "§11.2 — these three switches are off by default so the API authenticates/authorizes "
        "nobody out of the box). Never set this for a real deployment; it exists only so a "
        "prod-STAGE box mid-migration to enforce mode isn't hard-blocked from starting at all.",
    )
    openfga_api_url: str = Field(default="", validation_alias="OPENFGA_API_URL")
    openfga_store_id: str = Field(default="", validation_alias="OPENFGA_STORE_ID")
    openfga_api_token: str = Field(default="", validation_alias="OPENFGA_API_TOKEN")
    openfga_model_id: str = Field(default="", validation_alias="OPENFGA_MODEL_ID")
    keycloak_issuer: str = Field(default="", validation_alias="KEYCLOAK_ISSUER")
    keycloak_audience: str = Field(default="", validation_alias="KEYCLOAK_AUDIENCE")
    keycloak_client_id: str = Field(default="egregore-api", validation_alias="KEYCLOAK_CLIENT_ID")
    rbac_role_ingress: str = Field(default="egregore-ingress", validation_alias="RBAC_ROLE_INGRESS")
    rbac_role_operator: str = Field(default="egregore-operator", validation_alias="RBAC_ROLE_OPERATOR")
    rbac_role_gateway: str = Field(default="egregore-gateway", validation_alias="RBAC_ROLE_GATEWAY")
    rbac_role_reader: str = Field(default="egregore-reader", validation_alias="RBAC_ROLE_READER")
    gateway_access_token: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="GATEWAY_ACCESS_TOKEN",
    )

    auth_broker_url: str = Field(default="", validation_alias="BROKER_URL")
    auth_broker_service_token: str = Field(default="", validation_alias="BROKER_SERVICE_TOKEN")
    auth_broker_service_id: str = Field(default="egregore", validation_alias="BROKER_SERVICE_ID")
    auth_broker_audience: str = Field(default="veil-api", validation_alias="BROKER_VEIL_AUDIENCE")
    use_auth_broker: bool = Field(default=False, validation_alias="USE_AUTH_BROKER")

    api_gauge_refresh_interval_s: float = Field(
        default=30.0, validation_alias="API_GAUGE_REFRESH_INTERVAL_S"
    )
    api_reconcile_leader_ttl_s: int = Field(
        default=280, validation_alias="API_RECONCILE_LEADER_TTL_S"
    )
    api_reconcile_interval_s: float = Field(
        default=300.0, validation_alias="API_RECONCILE_INTERVAL_S"
    )
    api_sse_queue_timeout_s: float = Field(
        default=15.0, validation_alias="API_SSE_QUEUE_TIMEOUT_S"
    )
    api_sse_retry_sleep_s: float = Field(default=2.0, validation_alias="API_SSE_RETRY_SLEEP_S")
    api_sse_idle_sleep_s: float = Field(default=15.0, validation_alias="API_SSE_IDLE_SLEEP_S")

    http_connect_timeout_s: float = Field(default=5.0, validation_alias="HTTP_CONNECT_TIMEOUT_S")
    http_read_timeout_s: float = Field(default=30.0, validation_alias="HTTP_READ_TIMEOUT_S")

    worker_triage_max_attempts: int = Field(default=2, validation_alias="WORKER_TRIAGE_MAX_ATTEMPTS")
    worker_max_attempts: int = Field(default=3, validation_alias="WORKER_MAX_ATTEMPTS")
    worker_max_dependency_deferrals: int = Field(
        default=10, validation_alias="WORKER_MAX_DEPENDENCY_DEFERRALS"
    )
    worker_soft_timeout_fraction: float = Field(
        default=0.9, validation_alias="WORKER_SOFT_TIMEOUT_FRACTION"
    )
    worker_dequeue_timeout_s: float = Field(default=2.0, validation_alias="WORKER_DEQUEUE_TIMEOUT_S")
    execution_backend: str = Field(default="in_process", validation_alias="EXECUTION_BACKEND")

    reconcile_synthesis_stale_multiplier: float = Field(
        default=2.0, validation_alias="RECONCILE_SYNTHESIS_STALE_MULTIPLIER"
    )
    reconcile_scan_limit: int = Field(default=50, validation_alias="RECONCILE_SCAN_LIMIT")

    bus_seen_ttl_seconds: int = Field(default=300, validation_alias="BUS_SEEN_TTL_SECONDS")
    bus_redis_get_message_timeout_s: float = Field(
        default=1.0, validation_alias="BUS_REDIS_GET_MESSAGE_TIMEOUT_S"
    )
    bus_redis_subscriber_join_timeout_s: float = Field(
        default=2.0, validation_alias="BUS_REDIS_SUBSCRIBER_JOIN_TIMEOUT_S"
    )

    kafka_consume_timeout_s: float = Field(default=1.0, validation_alias="KAFKA_CONSUME_TIMEOUT_S")

    k8s_sandbox_ready_poll_interval_s: float = Field(
        default=0.5, validation_alias="K8S_SANDBOX_READY_POLL_INTERVAL_S"
    )
    docker_probe_timeout_s: float = Field(default=5.0, validation_alias="DOCKER_PROBE_TIMEOUT_S")
    docker_kill_timeout_s: float = Field(default=10.0, validation_alias="DOCKER_KILL_TIMEOUT_S")

    tool_output_preview_max: int = Field(default=16_384, validation_alias="TOOL_OUTPUT_PREVIEW_MAX")
    tool_stored_outputs_max: int = Field(default=5, validation_alias="TOOL_STORED_OUTPUTS_MAX")
    tool_siem_drilldown_max: int = Field(default=2, validation_alias="TOOL_SIEM_DRILLDOWN_MAX")

    run_attachment_max_bytes: int = Field(default=25 * 1024 * 1024, validation_alias="RUN_ATTACHMENT_MAX_BYTES")

    egress_batch_seconds: float = Field(default=0.05, validation_alias="EGRESS_BATCH_SECONDS")
    egress_output_preview_max: int = Field(default=800, validation_alias="EGRESS_OUTPUT_PREVIEW_MAX")

    timeout_salvage_summary_max: int = Field(
        default=2000, validation_alias="TIMEOUT_SALVAGE_SUMMARY_MAX"
    )

    follow_up_conversation_query_limit: int = Field(
        default=200, validation_alias="FOLLOW_UP_CONVERSATION_QUERY_LIMIT"
    )
    follow_up_history_limit: int = Field(default=100, validation_alias="FOLLOW_UP_HISTORY_LIMIT")
    follow_up_aggregator_timeout_s: float = Field(
        default=300.0, validation_alias="FOLLOW_UP_AGGREGATOR_TIMEOUT_S"
    )
    follow_up_aggregator_poll_s: float = Field(
        default=2.0, validation_alias="FOLLOW_UP_AGGREGATOR_POLL_S"
    )
    follow_up_merge_query_limit: int = Field(default=30, validation_alias="FOLLOW_UP_MERGE_QUERY_LIMIT")
    follow_up_merge_summary_max: int = Field(
        default=400, validation_alias="FOLLOW_UP_MERGE_SUMMARY_MAX"
    )

    wayback_api_timeout_s: float = Field(default=20.0, validation_alias="WAYBACK_API_TIMEOUT_S")

    critic_trust_threshold: float = Field(default=0.5, validation_alias="CRITIC_TRUST_THRESHOLD")
    critic_default_confidence: float = Field(
        default=0.5, validation_alias="CRITIC_DEFAULT_CONFIDENCE"
    )

    persona_budgets_overrides_json: str = Field(
        default="", validation_alias="PERSONA_BUDGETS_OVERRIDES_JSON"
    )
    planner_default_post_processors: str = Field(
        default="advisory_consultant_fallback,staged_soc_intel_for_incident",
        validation_alias="PLANNER_DEFAULT_POST_PROCESSORS",
    )
    default_persona_max_tool_calls: int = Field(
        default=50, validation_alias="DEFAULT_PERSONA_MAX_TOOL_CALLS"
    )

    engagement_egress_ttl_s: int = Field(default=86_400, validation_alias="ENGAGEMENT_EGRESS_TTL_S")
    engagement_egress_max_events: int = Field(
        default=200, validation_alias="ENGAGEMENT_EGRESS_MAX_EVENTS"
    )
    engagement_egress_pubsub_timeout_s: float = Field(
        default=1.0, validation_alias="ENGAGEMENT_EGRESS_PUBSUB_TIMEOUT_S"
    )
    engagement_egress_pubsub_idle_sleep_s: float = Field(
        default=0.05, validation_alias="ENGAGEMENT_EGRESS_PUBSUB_IDLE_SLEEP_S"
    )

    web_search_default_limit: int = Field(default=5, validation_alias="WEB_SEARCH_DEFAULT_LIMIT")
    duckduckgo_api_url: str = Field(
        default="https://api.duckduckgo.com/", validation_alias="DUCKDUCKGO_API_URL"
    )
    duckduckgo_api_timeout_s: float = Field(default=15.0, validation_alias="DUCKDUCKGO_API_TIMEOUT_S")
    serper_api_url: str = Field(
        default="https://google.serper.dev/search", validation_alias="SERPER_API_URL"
    )
    serper_api_timeout_s: float = Field(default=20.0, validation_alias="SERPER_API_TIMEOUT_S")

    perplexity_api_url: str = Field(
        default="https://api.perplexity.ai/chat/completions",
        validation_alias="PERPLEXITY_API_URL",
    )
    perplexity_api_timeout_s: float = Field(
        default=30.0, validation_alias="PERPLEXITY_API_TIMEOUT_S"
    )
    perplexity_search_default_limit: int = Field(
        default=5, validation_alias="PERPLEXITY_SEARCH_DEFAULT_LIMIT"
    )
    jina_search_api_url: str = Field(
        default="https://s.jina.ai/", validation_alias="JINA_SEARCH_API_URL"
    )
    jina_search_api_timeout_s: float = Field(
        default=30.0, validation_alias="JINA_SEARCH_API_TIMEOUT_S"
    )
    jina_search_default_limit: int = Field(default=5, validation_alias="JINA_SEARCH_DEFAULT_LIMIT")
    jina_search_snippet_max: int = Field(default=8000, validation_alias="JINA_SEARCH_SNIPPET_MAX")
    search_judge_input_max: int = Field(default=2000, validation_alias="SEARCH_JUDGE_INPUT_MAX")
    search_judge_prompt_max: int = Field(default=4000, validation_alias="SEARCH_JUDGE_PROMPT_MAX")

    siem_search_max_limit: int = Field(default=100, validation_alias="SIEM_SEARCH_MAX_LIMIT")
    siem_http_search_timeout_s: float = Field(
        default=10.0, validation_alias="SIEM_HTTP_SEARCH_TIMEOUT_S"
    )
    siem_search_default_time_range: str = Field(
        default="24h", validation_alias="SIEM_SEARCH_DEFAULT_TIME_RANGE"
    )
    siem_search_default_limit: int = Field(default=50, validation_alias="SIEM_SEARCH_DEFAULT_LIMIT")

    evidence_event_text_max: int = Field(default=500, validation_alias="EVIDENCE_EVENT_TEXT_MAX")
    evidence_max_confidence_metadata: float = Field(
        default=0.3, validation_alias="EVIDENCE_MAX_CONFIDENCE_METADATA"
    )
    evidence_max_confidence_sparse: float = Field(
        default=0.5, validation_alias="EVIDENCE_MAX_CONFIDENCE_SPARSE"
    )
    evidence_max_confidence_rich: float = Field(
        default=1.0, validation_alias="EVIDENCE_MAX_CONFIDENCE_RICH"
    )

    noop_low_confidence_threshold: float = Field(
        default=0.25, validation_alias="NOOP_LOW_CONFIDENCE_THRESHOLD"
    )
    noop_pending_trust_threshold: float = Field(
        default=0.3, validation_alias="NOOP_PENDING_TRUST_THRESHOLD"
    )

    egregore_metrics_port: int = Field(default=9091, validation_alias="EGREGORE_METRICS_PORT")

    ui_cors_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias="UI_CORS_ORIGINS",
    )

    @computed_field
    @property
    def ui_cors_origins(self) -> list[str]:
        return [part.strip() for part in self.ui_cors_origins_raw.split(",") if part.strip()]

    @model_validator(mode="before")
    @classmethod
    def normalize_ui_cors_origins(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = data.get("UI_CORS_ORIGINS") or data.get("ui_cors_origins_raw")
        if isinstance(raw, list):
            data = {**data, "UI_CORS_ORIGINS": ",".join(str(item) for item in raw)}
        return data

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in _ALLOWED_LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(_ALLOWED_LOG_LEVELS)}")
        return upper

    @model_validator(mode="after")
    def validate_runtime_config(self) -> Self:
        stage = self.stage.lower()
        if stage not in _ALLOWED_STAGES:
            raise ValueError(f"STAGE must be one of {sorted(_ALLOWED_STAGES)}")

        if self.log_format not in _ALLOWED_LOG_FORMATS:
            raise ValueError(f"LOG_FORMAT must be one of {sorted(_ALLOWED_LOG_FORMATS)}")

        control_mode = self.control_mode.lower()
        if control_mode not in _ALLOWED_CONTROL_MODES:
            raise ValueError(f"CONTROL_MODE must be one of {sorted(_ALLOWED_CONTROL_MODES)}")

        siem_adapter = self.siem_adapter.lower()
        if siem_adapter not in _ALLOWED_SIEM_ADAPTERS:
            raise ValueError(f"SIEM_ADAPTER must be one of {sorted(_ALLOWED_SIEM_ADAPTERS)}")

        sgr_mode = self.sgr_default_mode.lower()
        if sgr_mode not in _ALLOWED_SGR_MODES:
            raise ValueError(f"SGR_DEFAULT_MODE must be one of {sorted(_ALLOWED_SGR_MODES)}")

        for name, value in (
            ("PERSISTENCE_CONNECTOR", self.persistence_connector),
            ("JOB_STORE_CONNECTOR", self.job_store_connector),
            ("STATUS_STORE_CONNECTOR", self.status_store_connector),
            ("WORKSPACE_STORE_CONNECTOR", self.workspace_store_connector),
        ):
            normalized = value.lower()
            if normalized not in _ALLOWED_STORE_CONNECTORS:
                raise ValueError(f"{name} must be one of {sorted(_ALLOWED_STORE_CONNECTORS)}")

        if self.llm_request_timeout <= 0:
            raise ValueError("LLM_REQUEST_TIMEOUT must be positive")
        if self.worker_job_timeout <= 0:
            raise ValueError("WORKER_JOB_TIMEOUT must be positive")
        if self.worker_job_timeout < self.llm_request_timeout:
            raise ValueError("WORKER_JOB_TIMEOUT must be >= LLM_REQUEST_TIMEOUT")
        for name, value in (
            ("WORKER_JOB_TIMEOUT_INTEL", self.worker_job_timeout_intel),
            ("WORKER_JOB_TIMEOUT_SYNTH", self.worker_job_timeout_synth),
        ):
            if value > 0 and value < self.llm_request_timeout:
                raise ValueError(f"{name} must be >= LLM_REQUEST_TIMEOUT when set")

        if self.use_kafka and not self.kafka_bootstrap_servers.strip():
            raise ValueError("KAFKA_BOOTSTRAP_SERVERS is required when USE_KAFKA=1")

        if siem_adapter == "http" and not self.siem_base_url.strip():
            raise ValueError("SIEM_BASE_URL is required when SIEM_ADAPTER=http")

        if stage == "prod":
            if self.use_memory_fallback:
                raise ValueError("USE_MEMORY_FALLBACK must be false when STAGE=prod")
            if self.redis_password.get_secret_value() == _DEFAULT_REDIS_PASSWORD:
                raise ValueError("REDIS_PASSWORD must not use the default value in prod")
            if self.postgres_password.get_secret_value() == _DEFAULT_POSTGRES_PASSWORD:
                raise ValueError("POSTGRES_PASSWORD must not use the default value in prod")
            if self.bus_signing_key.get_secret_value() == _DEFAULT_BUS_SIGNING_KEY:
                raise ValueError("BUS_SIGNING_KEY must not use the default value in prod")
            if not self.allow_insecure_prod_authz:
                if not self.auth_enabled:
                    raise ValueError(
                        "AUTH_ENABLED must be true when STAGE=prod (see "
                        "docs/MICROSERVICES_SPLIT_PLAN.md §11.2) — set ALLOW_INSECURE_PROD_AUTHZ=1 "
                        "only for a deliberate, temporary exception"
                    )
                if self.authz_mode.lower() != "enforce":
                    raise ValueError(
                        "AUTHZ_MODE must be 'enforce' when STAGE=prod (see "
                        "docs/MICROSERVICES_SPLIT_PLAN.md §11.2) — set ALLOW_INSECURE_PROD_AUTHZ=1 "
                        "only for a deliberate, temporary exception"
                    )

        return self

    @model_validator(mode="after")
    def validate_auth_config(self) -> Self:
        if self.auth_enabled and not self.keycloak_issuer.strip():
            raise ValueError("KEYCLOAK_ISSUER is required when AUTH_ENABLED=1")
        if self.authz_mode.lower() not in _ALLOWED_AUTHZ_MODES:
            raise ValueError(f"AUTHZ_MODE must be one of {sorted(_ALLOWED_AUTHZ_MODES)}")
        self.authz_mode = self.authz_mode.lower()
        return self

    def resolve_worker_job_timeout(self, *, persona: str, phase: str | None = None) -> float:
        if phase == "synthesis" and self.worker_job_timeout_synth > 0:
            return self.worker_job_timeout_synth
        if persona == "intel" and self.worker_job_timeout_intel > 0:
            return self.worker_job_timeout_intel
        return self.worker_job_timeout

    @computed_field
    @property
    def llm_api_key(self) -> str:
        for key in (
            self.deepseek_api_key,
            self.openrouter_api_key,
            self.openai_api_key,
            self.anthropic_api_key,
            self.gemini_api_key,
            self.ai_apikey,
        ):
            if key:
                return key
        # LiteLLM openai/* routes require a non-empty api_key even for local vLLM.
        if self.llm_base_url:
            return "EMPTY"
        return ""

    @computed_field
    @property
    def postgres_url(self) -> str:
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def bus_signing_key_bytes(self) -> bytes:
        return self.bus_signing_key.get_secret_value().encode("utf-8")

    @computed_field
    @property
    def resolved_langfuse_public_key(self) -> str:
        return self.langfuse_public_key or self.langfuse_api_key

    @computed_field
    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.resolved_langfuse_public_key and self.langfuse_secret_key)

    @computed_field
    @property
    def resolved_langfuse_host(self) -> str:
        return self.langfuse_base_url or self.langfuse_host

    @computed_field
    @property
    def redis_url(self) -> str:
        password = self.redis_password.get_secret_value()
        if password:
            return f"redis://:{password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def __repr__(self) -> str:
        return (
            "Settings("
            f"stage={self.stage!r}, "
            f"use_kafka={self.use_kafka}, "
            f"control_mode={self.control_mode!r}, "
            f"auth_enabled={self.auth_enabled}"
            ")"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
