from __future__ import annotations

from typing import Protocol


class ContextSummarizerPort(Protocol):
    def summarize(self, *, goal: str, messages_text: str, prior_summary: str = "") -> str: ...
