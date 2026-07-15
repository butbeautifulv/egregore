from __future__ import annotations

from typing import Protocol

from langchain_core.language_models.chat_models import BaseChatModel


class ChatModelProvider(Protocol):
    """Provider-agnostic LLM factory (DIP)."""

    def create(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None,
        temperature: float,
        request_timeout: float,
        thinking_token_budget: int = 0,
    ) -> BaseChatModel: ...
