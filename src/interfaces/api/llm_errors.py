from __future__ import annotations

from fastapi import HTTPException


def is_llm_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in {"AuthenticationError", "APIConnectionError", "Timeout", "ServiceUnavailableError"}:
        return True
    module = type(exc).__module__ or ""
    if "litellm" in module:
        return True
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "litellm",
            "api key",
            "authentication",
            "connection error",
            "timeout",
            "model",
            "openai",
            "anthropic",
        )
    )


def raise_llm_unavailable(exc: BaseException) -> None:
    raise HTTPException(
        status_code=502,
        detail={"message": str(exc), "code": "llm_unavailable"},
    ) from exc
