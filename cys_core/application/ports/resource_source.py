from __future__ import annotations

from typing import Protocol


class ResourceSourcePort(Protocol):
    def list_worker_personas(self, profile_id: str | None = None) -> list[str]: ...
