from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import TypeVar

T = TypeVar("T")


def run_sync_from_sync_context(factory: Callable[[], Coroutine[object, object, T]]) -> T:
    """Run a coroutine factory from sync context; refuse when an event loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    raise RuntimeError(
        "Sync adapter called from a running event loop; use the async API instead"
    )
