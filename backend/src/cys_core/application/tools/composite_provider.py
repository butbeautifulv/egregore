from __future__ import annotations

from cys_core.application.ports.tool_provider import ToolProviderPort
from cys_core.domain.tools.models import ToolDefinitionView


class CompositeToolProvider:
    """Merge definitions from multiple providers; resolve via primary registry provider."""

    def __init__(
        self,
        *,
        primary: ToolProviderPort,
        metadata_providers: list[ToolProviderPort] | None = None,
    ) -> None:
        self._primary = primary
        self._metadata = metadata_providers or []

    @property
    def module_id(self) -> str:
        return self._primary.module_id

    def definitions(self, *, profile_id: str, persona: str = "") -> list[ToolDefinitionView]:
        merged: dict[str, ToolDefinitionView] = {}
        for provider in [*self._metadata, self._primary]:
            for item in provider.definitions(profile_id=profile_id, persona=persona):
                merged[item.name] = item
        return list(merged.values())

    def resolve(self, tool_names: list[str], *, profile_id: str, persona: str = "", sandbox_id: str = "") -> list:
        return self._primary.resolve(
            tool_names,
            profile_id=profile_id,
            persona=persona,
            sandbox_id=sandbox_id,
        )
