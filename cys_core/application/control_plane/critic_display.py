from __future__ import annotations

from typing import Any


def critic_verdict_visible_to_operator(result: dict[str, Any]) -> bool:
    """Surface critic in UI/SSE only when the gate changed operator-visible state."""
    if result.get("auto_accepted_after_revision_cap"):
        return True
    if not result.get("passed", True):
        return True
    if result.get("revision_enqueued"):
        return True
    return False


def format_critic_operator_message(
    result: dict[str, Any],
    *,
    source_persona: str,
) -> str:
    if result.get("auto_accepted_after_revision_cap"):
        return (
            f"Проверка агента {source_persona}: лимит доработок исчерпан, результат принят автоматически."
        )
    issues = list(result.get("issues_detected") or []) + list(result.get("rejected_claims") or [])
    issues_text = ", ".join(str(item) for item in issues if item) or "требования качества не выполнены"
    if result.get("revision_enqueued"):
        return (
            f"Проверка не пройдена ({source_persona}): {issues_text}. Запрошена доработка агента."
        )
    return f"Проверка не пройдена ({source_persona}): {issues_text}."
