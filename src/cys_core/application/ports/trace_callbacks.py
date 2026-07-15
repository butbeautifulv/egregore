from __future__ import annotations

from typing import Any, Callable, Protocol


class TraceCallbackProvider(Protocol):
    def callbacks(self) -> list[Any]: ...


_callback_provider: Callable[[], list[Any]] | None = None


def configure_trace_callbacks(provider: Callable[[], list[Any]]) -> None:
    global _callback_provider
    _callback_provider = provider


def get_trace_callbacks() -> list[Any]:
    if _callback_provider is None:
        return []
    return _callback_provider()
