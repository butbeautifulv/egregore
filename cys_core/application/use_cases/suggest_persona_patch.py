from __future__ import annotations

from typing import Callable

from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.catalog_write_gate import CatalogWriteGatePort
from cys_core.domain.catalog.models import AgentCatalogEntry, CatalogSource


class SuggestPersonaPatch:
    """Create a draft persona suggestion — never auto-applies to runtime."""

    def __init__(
        self,
        catalog: AgentCatalogPort,
        *,
        write_gate: CatalogWriteGatePort | None = None,
    ) -> None:
        self._catalog = catalog
        self._write_gate = write_gate

    def execute(
        self,
        name: str,
        *,
        description: str,
        system_prompt: str,
        profile_id: str = "cybersec-soc",
        language: str = "ru",
        actor: str = "api",
    ) -> AgentCatalogEntry:
        draft_name = f"{name}-draft"
        entry = AgentCatalogEntry(
            name=draft_name,
            description=description,
            persona_prompt=system_prompt,
            language=language,
            profile_id=profile_id,
            enabled=False,
            source=CatalogSource.API,
            tags=["draft-suggestion"],
            version_tag=f"suggest:{name}",
        )
        if self._write_gate is not None:
            return self._write_gate.upsert_agent(entry, actor=actor)
        return self._catalog.upsert_agent(entry)
