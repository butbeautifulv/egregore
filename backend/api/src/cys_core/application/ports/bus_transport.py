from __future__ import annotations

from typing import Any, Protocol

from cys_core.application.ports.managed_resource import Closeable


class BusTransportConnector(Closeable, Protocol):
    """Port for inter-agent bus transport adapters."""

    name: str
    requires_mtls: bool

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send an A2A message over the connector."""

    async def send_async(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send an A2A message asynchronously."""

    def subscribe(self, channel: str, handler: Any) -> None:
        """Register handler for bus messages on channel."""

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Publish message to bus channel."""
