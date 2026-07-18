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
    allow_insecure_prod_auth: bool = Field(
        default=False,
        validation_alias="ALLOW_INSECURE_PROD_AUTH",
        description="Explicit, temporary override to let STAGE=prod start with "
        "MODEL_GATEWAY_AUTH_ENABLED=0 (docs/MICROSERVICES_SPLIT_PLAN.md §11.2's prod-guard "
        "pattern, applied here — api/worker/tool-gateway all gate their own off-by-default "
        "auth toggle on STAGE=prod; this package's settings.py never got the same guard when "
        "it was built in §29). Never set this for a real deployment.",
    )

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
        if self.stage == "prod" and not self.auth_enabled and not self.allow_insecure_prod_auth:
            raise ValueError(
                "MODEL_GATEWAY_AUTH_ENABLED must be true when STAGE=prod (see "
                "docs/MICROSERVICES_SPLIT_PLAN.md §11.2) — set ALLOW_INSECURE_PROD_AUTH=1 "
                "only for a deliberate, temporary exception"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
