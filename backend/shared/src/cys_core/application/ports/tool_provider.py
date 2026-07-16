from __future__ import annotations

from typing import Protocol

from langchain_core.tools import BaseTool

from cys_core.domain.tools.models import ToolDefinitionView


class ToolProviderPort(Protocol):
    """Resolve tool definitions and LangChain tools for a profile/persona."""

    @property
    def module_id(self) -> str: ...

    def definitions(self, *, profile_id: str, persona: str = "") -> list[ToolDefinitionView]: ...

    def resolve(
        self,
        tool_names: list[str],
        *,
        profile_id: str,
        persona: str = "",
        sandbox_id: str = "",
    ) -> list[BaseTool]: ...
