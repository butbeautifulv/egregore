from __future__ import annotations

from cys_core.application.ports.context_summarizer import ContextSummarizerPort


class NoopContextSummarizer:
    def summarize(self, *, goal: str, messages_text: str, prior_summary: str = "") -> str:
        _ = goal, prior_summary
        if len(messages_text) <= 4000:
            return ""
        return messages_text[:4000] + "\n...[truncated]"


class LlmContextSummarizer:
    """Summarize long run context while preserving IOC/timeline facts."""

    def __init__(self, model_connector) -> None:
        self._connector = model_connector

    def summarize(self, *, goal: str, messages_text: str, prior_summary: str = "") -> str:
        if not messages_text.strip():
            return prior_summary
        model = self._connector.create_model()
        prompt = (
            "Summarize the investigation trace below for continuation. "
            "Preserve all IOCs, timestamps, hostnames, tool outputs, and open questions. "
            "Be concise but do not drop security-relevant facts.\n\n"
            f"Goal: {goal}\n"
        )
        if prior_summary:
            prompt += f"Prior summary:\n{prior_summary}\n\n"
        prompt += f"Trace:\n{messages_text[:12000]}"
        response = model.invoke(prompt)
        content = getattr(response, "content", str(response))
        return str(content).strip()
