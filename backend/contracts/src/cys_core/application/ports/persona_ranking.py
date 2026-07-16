from __future__ import annotations

from typing import Protocol


class PersonaRankingPort(Protocol):
    def rank(self, personas: list[str], *, profile_id: str = "cybersec-soc") -> list[str]: ...
