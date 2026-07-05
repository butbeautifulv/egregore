from __future__ import annotations

from typing import Any, Protocol


class ControlAgentHandler(Protocol):
    async def handle(self, envelope: dict[str, Any]) -> None: ...
