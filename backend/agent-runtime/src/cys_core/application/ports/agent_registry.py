from __future__ import annotations

from typing import Any, Protocol


class AgentRegistryPort(Protocol):
    def get(self, name: str) -> Any: ...

    def by_workers(self) -> list[Any]: ...

    def names(self) -> list[str]: ...
