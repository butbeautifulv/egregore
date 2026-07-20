from __future__ import annotations

from functools import lru_cache

from cys_core.application.ports.context_summarizer import ContextSummarizerPort
from cys_core.infrastructure.context.summarizer import LlmContextSummarizer, NoopContextSummarizer


@lru_cache
def get_context_summarizer() -> ContextSummarizerPort:
    try:
        from cys_core.llm import get_model_connector

        return LlmContextSummarizer(get_model_connector())
    except Exception:
        return NoopContextSummarizer()
