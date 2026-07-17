from __future__ import annotations

from typing import Any, Protocol


class ToolBackend(Protocol):
    """Port for gateway-backed tool implementations used by the tool registry."""

    def query_siem(self, query: str, time_range: str = "24h") -> dict[str, Any]: ...

    def rag_query(self, query: str, persona: str = "soc", tenant: str = "default") -> dict[str, Any]: ...
