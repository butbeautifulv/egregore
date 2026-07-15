from __future__ import annotations

from typing import Protocol

from cys_core.application.ports.managed_resource import Closeable


class RateLimiterPort(Closeable, Protocol):
    """Port for sliding-window rate limiting."""

    def allow(self, key: str) -> bool:
        """Return True when the key is within the configured limit."""

    def check(self, key: str) -> None:
        """Raise when the key exceeds the configured limit."""

    async def aallow(self, key: str) -> bool:
        """Async allow check."""

    async def acheck(self, key: str) -> None:
        """Async check that raises when over limit."""
