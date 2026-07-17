from __future__ import annotations

from typing import Any, Protocol


class AgentTransportConnector(Protocol):
    """Port for inter-agent transport connectors."""

    name: str
    requires_mtls: bool

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send an A2A message over the connector."""

    async def send_async(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send an A2A message over the connector asynchronously."""

    def subscribe(self, channel: str, handler: Any) -> None:
        """Register async handler for bus messages on channel."""

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Publish message to bus channel."""

    async def publish_delivery(self, message: dict[str, Any]) -> None:
        """Publish signed bus envelope for BusIngressRouter delivery."""
