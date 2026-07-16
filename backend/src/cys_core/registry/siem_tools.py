from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from cys_core.domain.tools.catalog.siem import SIEM_TOOL_DESCRIPTIONS as _SIEM_TOOL_DESCRIPTIONS
from cys_core.integrations.siem_mcp_client import get_siem_allowed_tools
from cys_core.registry.siem_tool_schemas import (
    GenericSiemToolInput,
    GetEventByUuidInput,
    InvestigateIncidentInput,
    ListIncidentsInput,
    SearchEventsInput,
)

_SIEM_TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "investigate_incident": InvestigateIncidentInput,
    "list_incidents": ListIncidentsInput,
    "search_events": SearchEventsInput,
    "get_event_by_uuid": GetEventByUuidInput,
}


def _invoke_siem_tool(name: str, args: dict[str, Any]) -> str:
    from cys_core.infrastructure.tools.adapters.siem_mcp import call_siem_tool

    result = call_siem_tool(name, args)
    return json.dumps(result, ensure_ascii=False)


async def _ainvoke_siem_tool(name: str, args: dict[str, Any]) -> str:
    from cys_core.infrastructure.tools.adapters.siem_mcp import acall_siem_tool

    result = await acall_siem_tool(name, args)
    return json.dumps(result, ensure_ascii=False)


def _make_typed_siem_tool(name: str, description: str, schema: type[BaseModel]) -> BaseTool:
    def _run(**kwargs: Any) -> str:
        return _invoke_siem_tool(name, kwargs)

    async def _arun(**kwargs: Any) -> str:
        return await _ainvoke_siem_tool(name, kwargs)

    return StructuredTool.from_function(
        func=_run,
        coroutine=_arun,
        name=name,
        description=description,
        args_schema=schema,
    )


def make_siem_tool(name: str, description: str) -> BaseTool:
    schema = _SIEM_TOOL_SCHEMAS.get(name)
    if schema is not None:
        return _make_typed_siem_tool(name, description, schema)

    def _run(**kwargs: Any) -> str:
        return _invoke_siem_tool(name, kwargs)

    async def _arun(**kwargs: Any) -> str:
        return await _ainvoke_siem_tool(name, kwargs)

    return StructuredTool.from_function(
        func=_run,
        coroutine=_arun,
        name=name,
        description=description,
        args_schema=GenericSiemToolInput,
    )


def _description_for_siem_tool(name: str, profile_id: str = "cybersec-soc") -> str:
    try:
        from cys_core.application.runtime_config import get_use_dynamic_catalog

        if not get_use_dynamic_catalog():
            raise RuntimeError("catalog not configured")
        from cys_core.infrastructure.catalog.registry_factory import get_tool_catalog

        entry = get_tool_catalog().get_tool(name, profile_id=profile_id)
        if entry and entry.description:
            return entry.description
    except Exception:
        pass
    return _SIEM_TOOL_DESCRIPTIONS.get(name, f"MaxPatrol SIEM MCP tool: {name}")


def build_siem_tools(*, profile_id: str = "cybersec-soc") -> list[BaseTool]:
    tools: list[BaseTool] = []
    for name in sorted(get_siem_allowed_tools(profile_id)):
        desc = _description_for_siem_tool(name, profile_id)
        tools.append(make_siem_tool(name, desc))
    return tools
