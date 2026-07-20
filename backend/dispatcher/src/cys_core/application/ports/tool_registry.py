from __future__ import annotations

from typing import Any, Protocol


class ToolRegistryPort(Protocol):
    def get(self, name: str) -> Any: ...

    def names(self, *, profile_id: str | None = None) -> list[str]: ...

    def resolve(self, names: list[str], profile_id: str = "cybersec-soc") -> list[Any]: ...
