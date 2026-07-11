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
_DEFAULT_REDIS_PASSWORD = "password"
_DEFAULT_POSTGRES_PASSWORD = "password"
_DEFAULT_BUS_SIGNING_KEY = "cys-agi-bus-key"


def _settings_env_files() -> tuple[str, ...]:
    """Load repo-local secrets after .env (same file sourced by scripts/dev.sh)."""
    files: list[str] = [".env"]
    override = (Path.cwd() / ".env").resolve()
    if override.name == ".env" and override.is_file() and str(override) not in files:
        files[0] = str(override)

    repo_root = Path(__file__).resolve().parents[3]
    local_secrets = repo_root / "deploy" / ".secrets" / "egregore-local.env"
    if local_secrets.is_file():
        files.append(str(local_secrets))
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
    postgres_db: str = Field(default="cys_agi", validation_alias="POSTGRES_DB")

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
    critic_use_llm_judge: bool = Field(default=False, validation_alias="CRITIC_USE_LLM_JUDGE")
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

    ui_cors_origins_raw: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173",
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

        return self

    @model_validator(mode="after")
    def validate_auth_config(self) -> Self:
        if self.auth_enabled and not self.keycloak_issuer.strip():
            raise ValueError("KEYCLOAK_ISSUER is required when AUTH_ENABLED=1")
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
