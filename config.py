from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM providers (first non-empty key is used)
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
    agents_root: str = Field(default="agents", validation_alias="AGENTS_ROOT")

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
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
