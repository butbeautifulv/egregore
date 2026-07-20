from __future__ import annotations

from typing import Any, Protocol


class BusReloadCallback(Protocol):
    def __call__(self, registry: Any) -> None: ...
