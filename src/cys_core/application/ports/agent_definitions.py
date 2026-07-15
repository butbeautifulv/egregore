from __future__ import annotations

from pathlib import Path
from typing import Protocol

from cys_core.domain.agents.models import AgentDefinition


class AgentDefinitionsLoaderPort(Protocol):
    def load(self, root: Path | None = None) -> dict[str, AgentDefinition]: ...
