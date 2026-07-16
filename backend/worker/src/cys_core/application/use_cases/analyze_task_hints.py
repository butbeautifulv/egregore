from __future__ import annotations

from typing import Protocol


class TaskHintsModel(Protocol):
    def invoke(self, prompt: str) -> object: ...


_SOC_HINTS_PROMPT = """You are a SOC investigation advisor. Review the task below and list subtle pitfalls:
- ambiguous IOCs or missing context (host role, time window, data source)
- false-positive traps (benign admin tools, expected automation)
- evidence gaps that should be clarified before tool use
- scope or authorization risks

Task:
{task}

Respond with 3-6 concise bullet points. If nothing notable, reply with "No major pitfalls detected."
"""


class AnalyzeTaskHints:
    """Pre-task hints pass (DeepAgent QAHandler pattern, SOC-focused)."""

    def __init__(self, model: TaskHintsModel | None = None) -> None:
        self._model = model

    def execute(self, task: str) -> list[str]:
        if not task.strip():
            return []
        if self._model is None:
            return _heuristic_hints(task)
        prompt = _SOC_HINTS_PROMPT.format(task=task.strip())
        response = self._model.invoke(prompt)
        text = str(getattr(response, "content", response)).strip()
        if not text or "no major pitfalls" in text.lower():
            return []
        lines = [line.strip().lstrip("-•* ").strip() for line in text.splitlines() if line.strip()]
        return [line for line in lines if line]


def _heuristic_hints(task: str) -> list[str]:
    lower = task.lower()
    hints: list[str] = []
    if any(token in lower for token in ("ip", "domain", "hash")) and "time" not in lower:
        hints.append("IOC present but time window may be unspecified — confirm lookback period.")
    if "powershell" in lower or "encoded" in lower:
        hints.append("Encoded PowerShell alerts are often noisy — verify parent process and user context.")
    if "critical" in lower or "urgent" in lower:
        hints.append("High-severity language detected — validate scope before destructive actions.")
    return hints
