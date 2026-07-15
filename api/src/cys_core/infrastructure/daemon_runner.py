from __future__ import annotations

import asyncio
import signal
from collections.abc import Awaitable, Callable


async def run_poll_daemon(
    process_one: Callable[[float], Awaitable[bool]],
    *,
    idle_timeout: float = 30.0,
    poll_interval: float = 1.0,
    idle_sleep: Callable[[float], Awaitable[None]] | None = None,
    request_stop: Callable[[], None] | None = None,
) -> int:
    """Shared idle-timeout daemon loop for router, bus, and worker consumers."""
    stop = False

    def _request_stop() -> None:
        nonlocal stop
        stop = True
        if request_stop is not None:
            request_stop()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _request_stop)

    processed = 0
    idle_elapsed = 0.0
    while not stop:
        handled = await process_one(poll_interval)
        if handled:
            processed += 1
            idle_elapsed = 0.0
            continue
        idle_elapsed += poll_interval
        if idle_timeout > 0 and idle_elapsed >= idle_timeout:
            break
        if idle_sleep is not None:
            await idle_sleep(poll_interval)
    return processed
