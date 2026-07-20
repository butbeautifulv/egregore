from __future__ import annotations

from pathlib import Path

from bootstrap.product_loader import load_agent_definitions
from cys_core.application.ports.agent_definitions import AgentDefinitionsLoaderPort
from cys_core.domain.agents.models import AgentDefinition


class BootstrapAgentDefinitionsLoader:
    def load(self, root: Path | None = None) -> dict[str, AgentDefinition]:
        return load_agent_definitions(root)


def get_default_agent_definitions_loader() -> AgentDefinitionsLoaderPort:
    return BootstrapAgentDefinitionsLoader()
