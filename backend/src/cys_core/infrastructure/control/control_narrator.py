from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol


class NarratorRuntimePort(Protocol):
    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        tenant_id: str | None = None,
        investigation_id: str | None = None,
    ) -> dict[str, Any]: ...


def _finding_from_context(context: dict[str, Any]) -> dict[str, Any] | None:
    finding = context.get("finding")
    return finding if isinstance(finding, dict) else None


class TemplateControlNarrator:
    """Template-based coordinator narrative without LLM runtime."""

    def __init__(self, *, narrate_fn: Callable[..., Awaitable[str]]) -> None:
        self._narrate_fn = narrate_fn

    async def narrate(self, context: dict[str, Any]) -> str:
        return await self._narrate_fn(
            sender=str(context.get("sender", "unknown")),
            event_id=str(context.get("event_id", "n/a")),
            tenant_id=str(context.get("tenant_id", "default")),
            investigation_id=str(context.get("investigation_id", "")),
            finding=_finding_from_context(context),
        )


class LlmControlNarrator:
    """Optional LLM-backed narrator for worker/control pods."""

    def __init__(self, *, narrate_fn: Callable[..., Awaitable[str]]) -> None:
        self._narrate_fn = narrate_fn

    async def narrate(self, context: dict[str, Any]) -> str:
        return await self._narrate_fn(
            sender=str(context.get("sender", "unknown")),
            event_id=str(context.get("event_id", "n/a")),
            tenant_id=str(context.get("tenant_id", "default")),
            investigation_id=str(context.get("investigation_id", "")),
            finding=_finding_from_context(context),
        )
