from __future__ import annotations

from typing import Any, Protocol


class NarrationPort(Protocol):
    async def narrate(self, context: dict[str, Any]) -> str: ...
