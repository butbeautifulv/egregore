from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_STAGES = frozenset({"dev", "test", "staging", "prod"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    stage: str = Field(default="dev", validation_alias="STAGE")
    host: str = Field(default="0.0.0.0", validation_alias="MODEL_GATEWAY_HOST")
    port: int = Field(default=8093, validation_alias="MODEL_GATEWAY_PORT")

    # Defense-in-depth bearer check, same off-by-default shape as tool-gateway's
    # auth_enabled — the real guarantee is the NetworkPolicy egress restriction
    # (§10.8/§22.9), not this. Off by default so local/dev doesn't need a secret.
    auth_enabled: bool = Field(default=False, validation_alias="MODEL_GATEWAY_AUTH_ENABLED")
    shared_secret: str = Field(default="", validation_alias="MODEL_GATEWAY_SHARED_SECRET")

    # litellm model routing — same shape as worker's LlmSettings (model name,
    # provider creds resolved by litellm itself from its own env vars, e.g.
    # OPENAI_API_KEY/ANTHROPIC_API_KEY — not duplicated here).
    default_model: str = Field(default="gpt-4o-mini", validation_alias="MODEL_GATEWAY_DEFAULT_MODEL")
    request_timeout_s: float = Field(default=60.0, validation_alias="MODEL_GATEWAY_REQUEST_TIMEOUT_S")
    num_retries: int = Field(default=2, validation_alias="MODEL_GATEWAY_NUM_RETRIES")

    def model_post_init(self, _context: object) -> None:
        if self.stage.lower() not in _ALLOWED_STAGES:
            raise ValueError(f"invalid stage: {self.stage!r}")
        object.__setattr__(self, "stage", self.stage.lower())
        if self.auth_enabled and not self.shared_secret:
            raise ValueError("MODEL_GATEWAY_AUTH_ENABLED=true requires MODEL_GATEWAY_SHARED_SECRET")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
