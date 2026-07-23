from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog

from bootstrap.settings import get_settings
from cys_core.application.use_cases.invoke_model import InvokeModel

logger = structlog.get_logger(__name__)


def _serialize_tool_calls(message: Any) -> list[dict[str, Any]]:
    raw_tool_calls = getattr(message, "tool_calls", None) or []
    calls: list[dict[str, Any]] = []
    for call in raw_tool_calls:
        fn = getattr(call, "function", None)
        calls.append(
            {
                "id": getattr(call, "id", "") or "",
                "type": "function",
                "function": {
                    "name": getattr(fn, "name", "") or "",
                    "arguments": getattr(fn, "arguments", "") or "",
                },
            }
        )
    return calls


async def _litellm_complete(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float | None,
    max_tokens: int | None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    import litellm

    settings = get_settings()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "timeout": settings.request_timeout_s,
    }
    if settings.num_retries > 0:
        kwargs["num_retries"] = settings.num_retries
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if tools:
        kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
    response = await litellm.acompletion(**kwargs)
    choice = response.choices[0]
    content = choice.message.content or ""
    usage = getattr(response, "usage", None)
    usage_dict = usage.model_dump() if usage is not None and hasattr(usage, "model_dump") else {}
    return {
        "content": content,
        "usage": usage_dict,
        "tool_calls": _serialize_tool_calls(choice.message),
    }


class Container:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._rate_limiter = None

    def _get_rate_limiter(self):
        if self._rate_limiter is None:
            from bootstrap.rate_limit import RedisSlidingWindowRateLimiter

            self._rate_limiter = RedisSlidingWindowRateLimiter(
                redis_url=self.settings.redis_url,
                max_calls=self.settings.max_calls_per_window,
                window_seconds=self.settings.rate_limit_window_seconds,
            )
        return self._rate_limiter

    async def _check_model_rate_limit(self, command) -> None:
        mode = self.settings.rate_limit_mode
        if mode == "off":
            return
        try:
            await self._get_rate_limiter().check(f"{command.persona}:{command.session_id}")
        except Exception as exc:
            if mode == "shadow":
                logger.warning("model_gateway_rate_limit_shadow", persona=command.persona, error=str(exc))
                return
            raise

    def get_invoke_model(self) -> InvokeModel:
        return InvokeModel(
            complete=_litellm_complete,
            default_model=self.settings.default_model,
            check_rate_limit=self._check_model_rate_limit,
        )


@lru_cache(maxsize=1)
def get_container() -> Container:
    return Container()
