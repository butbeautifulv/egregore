from __future__ import annotations

from typing import Any, Protocol


class SchemaRegistryPort(Protocol):
    def get(self, name: str | None) -> Any: ...
