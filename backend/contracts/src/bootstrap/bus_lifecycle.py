from __future__ import annotations

import asyncio

from bootstrap.container import ensure_bus_router_wired
from cys_core.infrastructure.bus_transport import DELIVERY_TOPIC, get_bus_transport, set_bus_main_event_loop


async def wire_async_bus() -> None:
    """Register main loop, wire bus router, and start Redis subscriber when available."""
    set_bus_main_event_loop(asyncio.get_running_loop())
    ensure_bus_router_wired()
    transport = get_bus_transport()
    start_subscriber = getattr(transport, "start_subscriber_loop", None)
    if start_subscriber is not None:
        start_subscriber([DELIVERY_TOPIC])
