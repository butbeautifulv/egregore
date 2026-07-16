from __future__ import annotations

import asyncio

from cys_core.infrastructure.bus_transport import DELIVERY_TOPIC, get_bus_transport, set_bus_main_event_loop


async def wire_async_bus() -> None:
    """Register main loop, wire bus router (if this service has one), and
    start Redis subscriber when available.

    Called from both api's app.py (needs the transport subscriber, e.g. for
    status/SSE) and worker's daemon.py (also needs actual bus-message
    routing to control-plane handlers). bootstrap.container is polymorphic
    (api/worker each have their own Container) — api's has no
    wire_bus_router()/ensure_bus_router_wired concept (control-plane bus
    routing is worker-only, see plan §2), so that half of this is optional,
    not both a lazy import and an optional call.
    """
    set_bus_main_event_loop(asyncio.get_running_loop())
    from bootstrap.container import get_container  # ty: ignore[unresolved-import]

    wire_bus_router = getattr(get_container(), "wire_bus_router", None)
    if wire_bus_router is not None:
        wire_bus_router()
    transport = get_bus_transport()
    start_subscriber = getattr(transport, "start_subscriber_loop", None)
    if start_subscriber is not None:
        start_subscriber([DELIVERY_TOPIC])
