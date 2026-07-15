from __future__ import annotations

from typing import Protocol


class SkillRegistryPort(Protocol):
    def list_metadata(self, profile_id: str = "") -> list[dict[str, str]]: ...
