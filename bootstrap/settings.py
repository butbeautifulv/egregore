from functools import lru_cache
from typing import Self

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    ai_apikey: str = Field(default="", validation_alias="AI_APIKEY")

    llm_provider: str = Field(default="litellm", validation_alias="LLM_PROVIDER")
    llm_model: str = Field(default="anthropic/claude-sonnet-4", validation_alias="LLM_MODEL")
    llm_base_url: str | None = Field(default=None, validation_alias="LLM_BASE_URL")
    llm_temperature: float = Field(default=0.1, validation_alias="LLM_TEMPERATURE")

    stage: str = Field(default="dev", validation_alias="STAGE")

    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_password: str = Field(default="password", validation_alias="REDIS_PASSWORD")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")

    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="password", validation_alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="cys_agi", validation_alias="POSTGRES_DB")

    langfuse_api_key: str = Field(default="", validation_alias="LANGFUSE_API_KEY")
    langfuse_host: str = Field(default="http://localhost:3000", validation_alias="LANGFUSE_HOST")

    hitl_auto_approve_threshold: str = Field(default="low", validation_alias="HITL_AUTO_APPROVE_THRESHOLD")
    max_tool_calls_per_minute: int = Field(default=30, validation_alias="MAX_TOOL_CALLS_PER_MINUTE")
    trust_score_threshold: float = Field(default=0.5, validation_alias="TRUST_SCORE_THRESHOLD")
    use_memory_fallback: bool = Field(default=False, validation_alias="USE_MEMORY_FALLBACK")
    persistence_connector: str = Field(default="auto", validation_alias="PERSISTENCE_CONNECTOR")
    job_store_connector: str = Field(default="auto", validation_alias="JOB_STORE_CONNECTOR")
    bus_signing_key: str = Field(default="cys-agi-bus-key", validation_alias="BUS_SIGNING_KEY")
    siem_adapter: str = Field(default="mock", validation_alias="SIEM_ADAPTER")
    siem_base_url: str = Field(default="", validation_alias="SIEM_BASE_URL")
    use_real_embeddings: bool = Field(default=False, validation_alias="USE_REAL_EMBEDDINGS")
    agents_root: str = Field(default="agents", validation_alias="AGENTS_ROOT")

    kafka_bootstrap_servers: str = Field(
        default="localhost:19092",
        validation_alias="KAFKA_BOOTSTRAP_SERVERS",
    )
    use_kafka: bool = Field(default=False, validation_alias="USE_KAFKA")

    tool_gateway_url: str = Field(
        default="http://localhost:8090",
        validation_alias="TOOL_GATEWAY_URL",
    )
    use_tool_gateway: bool = Field(default=False, validation_alias="USE_TOOL_GATEWAY")

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

    auth_enabled: bool = Field(default=False, validation_alias="AUTH_ENABLED")
    rbac_enabled: bool = Field(default=False, validation_alias="RBAC_ENABLED")
    keycloak_issuer: str = Field(default="", validation_alias="KEYCLOAK_ISSUER")
    keycloak_audience: str = Field(default="", validation_alias="KEYCLOAK_AUDIENCE")
    keycloak_client_id: str = Field(default="egregore-api", validation_alias="KEYCLOAK_CLIENT_ID")
    rbac_role_ingress: str = Field(default="egregore-ingress", validation_alias="RBAC_ROLE_INGRESS")
    rbac_role_operator: str = Field(default="egregore-operator", validation_alias="RBAC_ROLE_OPERATOR")
    rbac_role_gateway: str = Field(default="egregore-gateway", validation_alias="RBAC_ROLE_GATEWAY")
    rbac_role_reader: str = Field(default="egregore-reader", validation_alias="RBAC_ROLE_READER")
    gateway_access_token: str = Field(default="", validation_alias="GATEWAY_ACCESS_TOKEN")

    @model_validator(mode="after")
    def validate_auth_config(self) -> Self:
        if self.auth_enabled and not self.keycloak_issuer.strip():
            raise ValueError("KEYCLOAK_ISSUER is required when AUTH_ENABLED=1")
        return self

    @computed_field
    @property
    def llm_api_key(self) -> str:
        for key in (
            self.openrouter_api_key,
            self.openai_api_key,
            self.anthropic_api_key,
            self.gemini_api_key,
            self.ai_apikey,
        ):
            if key:
                return key
        return ""

    @computed_field
    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def bus_signing_key_bytes(self) -> bytes:
        return self.bus_signing_key.encode("utf-8")

    @computed_field
    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
