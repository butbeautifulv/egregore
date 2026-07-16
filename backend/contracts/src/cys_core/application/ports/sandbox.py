from __future__ import annotations

from typing import Any, Protocol


class SandboxConnector(Protocol):
    """Port for ephemeral worker sandbox lifecycle."""

    name: str

    def create(self, run_id: str, persona: str, policy: str = "default") -> Any:
        """Provision isolated sandbox for one worker run."""

    def destroy(self, run_id: str) -> None:
        """Tear down sandbox after worker completes."""

    async def acreate(self, run_id: str, persona: str, policy: str = "default") -> Any:
        """Async provision sandbox."""

    async def adestroy(self, run_id: str) -> None:
        """Async tear down sandbox."""
