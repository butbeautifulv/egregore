from __future__ import annotations

from typing import Any, Protocol


class ControlNarratorPort(Protocol):
    """Lightweight LLM narration for coordinator control agent."""

    async def narrate(self, context: dict[str, Any]) -> str: ...
