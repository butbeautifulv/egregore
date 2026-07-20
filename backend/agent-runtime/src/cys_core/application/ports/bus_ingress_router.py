from __future__ import annotations

from typing import Any, Protocol


class BusIngressRouterPort(Protocol):
    """Route signed bus envelopes to control handlers or orchestration queue."""

    async def route_envelope(self, envelope: dict[str, Any]) -> None: ...
