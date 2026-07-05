from __future__ import annotations

from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import ChatResult, LLMResult

from cys_core.domain.workers.job_budget import JobBudgetExceeded, JobBudgetTracker
from cys_core.infrastructure.observability.egress_streaming_callback import _extract_generation_text, _iter_generations


def _usage_from_response(response: LLMResult | ChatResult) -> tuple[int, int]:
    prompt_tokens = 0
    completion_tokens = 0
    llm_output = getattr(response, "llm_output", None) or {}
    if isinstance(llm_output, dict):
        token_usage = llm_output.get("token_usage") or {}
        if isinstance(token_usage, dict):
            prompt_tokens = int(token_usage.get("prompt_tokens") or 0)
            completion_tokens = int(token_usage.get("completion_tokens") or 0)
    for gen in _iter_generations(response):
        message = getattr(gen, "message", None)
        usage_metadata = getattr(message, "usage_metadata", None) if message is not None else None
        if isinstance(usage_metadata, dict):
            prompt_tokens = int(usage_metadata.get("input_tokens") or usage_metadata.get("prompt_tokens") or prompt_tokens)
            completion_tokens = int(
                usage_metadata.get("output_tokens") or usage_metadata.get("completion_tokens") or completion_tokens
            )
    return prompt_tokens, completion_tokens


class BudgetUsageCallback(AsyncCallbackHandler):
    """Record real LLM token usage into JobBudgetTracker from LangChain callbacks."""

    def __init__(self, session_id: str, *, use_api_usage: bool = True) -> None:
        super().__init__()
        self._session_id = session_id
        self._use_api_usage = use_api_usage

    def _record(self, response: LLMResult | ChatResult) -> None:
        if not self._session_id:
            return
        prompt_tokens, completion_tokens = _usage_from_response(response)
        total = prompt_tokens + completion_tokens
        if total <= 0:
            text = _extract_generation_text(response)
            if text:
                total = JobBudgetTracker.estimate_tokens(text)
        if total > 0:
            JobBudgetTracker.record_tokens(self._session_id, total)

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if self._use_api_usage:
            try:
                self._record(response)
            except JobBudgetExceeded:
                pass

    async def on_chat_model_end(self, response: ChatResult, **kwargs: Any) -> None:
        if self._use_api_usage:
            try:
                self._record(response)
            except JobBudgetExceeded:
                pass


def build_budget_usage_callback(session_id: str, *, use_api_usage: bool = True) -> BudgetUsageCallback:
    return BudgetUsageCallback(session_id, use_api_usage=use_api_usage)
