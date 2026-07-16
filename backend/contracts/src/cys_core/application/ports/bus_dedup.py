from __future__ import annotations

from typing import Protocol


class BusDedupPort(Protocol):
    def is_duplicate(self, fingerprint: str) -> bool: ...
