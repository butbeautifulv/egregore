from __future__ import annotations

from cys_core.domain.authz.tool_datasource_map import TOOL_TO_DATASOURCE
from cys_core.domain.datasources.models import DataSourceCapability
from cys_core.domain.datasources.tool_metadata import ToolDataSourceBinding

_AUTHZ_MAP_BINDINGS: dict[str, ToolDataSourceBinding] = {
    tool_name: ToolDataSourceBinding(
        tool_name=tool_name,
        datasource_id=datasource_id,
        capability=DataSourceCapability.QUERY,
        description=f"Read-only access to {datasource_id}",
    )
    for tool_name, datasource_id in TOOL_TO_DATASOURCE.items()
}

DATASOURCE_TOOL_BINDINGS: dict[str, ToolDataSourceBinding] = {
    **_AUTHZ_MAP_BINDINGS,
    "query_siem_readonly": ToolDataSourceBinding(
        tool_name="query_siem_readonly",
        datasource_id="siem-readonly",
        capability=DataSourceCapability.QUERY,
        description="Read-only SIEM search",
    ),
    "rag_query": ToolDataSourceBinding(
        tool_name="rag_query",
        datasource_id="rag-index",
        capability=DataSourceCapability.QUERY,
        description="Read-only RAG retrieval",
    ),
}


def get_tool_datasource_binding(tool_name: str) -> ToolDataSourceBinding | None:
    return DATASOURCE_TOOL_BINDINGS.get(tool_name)


def is_get_only_binding(binding: ToolDataSourceBinding) -> bool:
    return binding.capability in {DataSourceCapability.GET, DataSourceCapability.LIST}
