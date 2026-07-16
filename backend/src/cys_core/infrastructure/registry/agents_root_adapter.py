from __future__ import annotations

from pathlib import Path

from cys_core.application.ports.agents_root import AgentsRootPort
from cys_core.registry.product_context import default_agents_root


class AgentsRootAdapter:
    def agents_root(self) -> Path:
        return default_agents_root()


def build_agents_root_port() -> AgentsRootPort:
    return AgentsRootAdapter()
