from __future__ import annotations

from pathlib import Path
from typing import Protocol


class AgentsRootPort(Protocol):
    def agents_root(self) -> Path: ...
