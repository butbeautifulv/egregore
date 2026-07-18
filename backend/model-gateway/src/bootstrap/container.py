from __future__ import annotations

from functools import lru_cache
from typing import Any

from bootstrap.settings import get_settings
from cys_core.application.use_cases.invoke_model import InvokeModel


async def _litellm_complete(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float | None,
    max_tokens: int | None,
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
    response = await litellm.acompletion(**kwargs)
    choice = response.choices[0]
    content = choice.message.content or ""
    usage = getattr(response, "usage", None)
    usage_dict = usage.model_dump() if usage is not None and hasattr(usage, "model_dump") else {}
    return {"content": content, "usage": usage_dict}


class Container:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_invoke_model(self) -> InvokeModel:
        return InvokeModel(
            complete=_litellm_complete,
            default_model=self.settings.default_model,
        )


@lru_cache(maxsize=1)
def get_container() -> Container:
    return Container()
