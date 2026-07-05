from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class CatalogSingletons:
    _lock = threading.RLock()
    _instances: dict[str, object] = {}

    @classmethod
    def get(cls, name: str, factory: Callable[[], T]) -> T:
        with cls._lock:
            if name not in cls._instances:
                cls._instances[name] = factory()
            return cls._instances[name]  # type: ignore[return-value]

    @classmethod
    def reset(cls, *names: str) -> None:
        with cls._lock:
            if names:
                for name in names:
                    cls._instances.pop(name, None)
            else:
                cls._instances.clear()
