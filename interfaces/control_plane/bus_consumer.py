from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from cys_core.infrastructure.daemon_runner import run_poll_daemon
from cys_core.infrastructure.kafka_bus_events import consume_bus_finding

BusHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None] | dict[str, Any] | None]


class BusFindingsConsumer:
    """Consume bus.findings and dispatch to control-plane handlers by channel."""

    def __init__(
        self,
        channel: str,
        handler: BusHandler,
        *,
        group_id: str | None = None,
        consume: Callable[..., Awaitable[dict[str, Any] | None]] | None = None,
    ) -> None:
        self.channel = channel
        self.handler = handler
        self.group_id = group_id or f"control-{channel}"
        self._consume = consume or consume_bus_finding
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def _matches_channel(self, envelope: dict[str, Any]) -> bool:
        return envelope.get("channel") == self.channel or envelope.get("recipient") == self.channel

    async def process_one(self, timeout: float = 1.0) -> bool:
        envelope = await self._consume(timeout=timeout, group_id=self.group_id)
        if envelope is None or not self._matches_channel(envelope):
            return False
        result = self.handler(envelope)
        if hasattr(result, "__await__"):
            await result
        return True

    async def run(self, *, idle_timeout: float = 30.0) -> int:
        return await run_poll_daemon(
            self.process_one,
            idle_timeout=idle_timeout,
            request_stop=self.request_stop,
        )


def run_bus_consumer(
    channel: str,
    handler: BusHandler,
    *,
    idle_timeout: float = 0.0,
    group_id: str | None = None,
) -> int:
    return asyncio.run(BusFindingsConsumer(channel, handler, group_id=group_id).run(idle_timeout=idle_timeout))
