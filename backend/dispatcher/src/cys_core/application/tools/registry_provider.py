from __future__ import annotations

from langchain_core.tools import BaseTool

from cys_core.application.datasources.attach_filter import filter_attachable_tools
from cys_core.application.ports.tool_registry import ToolRegistryPort
from cys_core.application.tools.providers import ALL_PROVIDER_DEFINITIONS, MODULE_BY_TOOL_NAME, status_for_tool
from cys_core.application.tools.tool_schema_exporter import ToolSchemaExporter
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus

_MODULE_DEFINITIONS: list[ToolDefinitionView] = ALL_PROVIDER_DEFINITIONS
_MODULE_BY_NAME: dict[str, ToolDefinitionView] = MODULE_BY_TOOL_NAME


def _status_for(tool_name: str) -> ToolStatus:
    return status_for_tool(tool_name)


class RegistryToolProvider:
    """Default provider composing registry tools with module metadata."""

    module_id = "builtin"

    def __init__(
        self,
        tool_registry: ToolRegistryPort,
        exporter: ToolSchemaExporter | None = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._exporter = exporter or ToolSchemaExporter()

    def definitions(self, *, profile_id: str, persona: str = "") -> list[ToolDefinitionView]:
        from cys_core.domain.security.profile_tools import filter_tools_for_profile

        names = filter_tools_for_profile(self._tool_registry.names(), profile_id)
        views: list[ToolDefinitionView] = []
        for name in names:
            module_def = _MODULE_BY_NAME.get(name)
            tool = self._tool_registry.get(name)
            schema = self._exporter.export_tool(name, self._tool_registry) or {}
            views.append(
                ToolDefinitionView(
                    name=name,
                    description=getattr(tool, "description", "") or "",
                    status=_status_for(name),
                    module=module_def.module if module_def else "builtin",
                    datasource_id=module_def.datasource_id if module_def else "",
                    json_schema=schema,
                )
            )
        _ = persona
        return views

    def resolve(
        self,
        tool_names: list[str],
        *,
        profile_id: str = DEFAULT_PROFILE_ID,
        persona: str = "",
        sandbox_id: str = "",
    ) -> list[BaseTool]:
        _ = sandbox_id
        filtered = filter_attachable_tools(tool_names, profile_id=profile_id, persona=persona)
        return self._tool_registry.resolve(filtered, profile_id=profile_id)


_default_provider: RegistryToolProvider | None = None


def configure_default_tool_provider(provider: RegistryToolProvider) -> None:
    global _default_provider
    _default_provider = provider


def get_default_tool_provider() -> RegistryToolProvider:
    if _default_provider is None:
        raise RuntimeError("Default tool provider not configured — wire via bootstrap Container")
    return _default_provider
