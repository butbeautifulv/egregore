from __future__ import annotations

import json
from typing import Any

import httpx
from langchain_core.tools import BaseTool, StructuredTool

from bootstrap.settings import settings
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import inject_correlation_headers
from cys_core.registry.tools import tool_registry


def require_sandbox(sandbox_id: str) -> None:
    if not sandbox_id or sandbox_id == "host":
        raise PermissionError("Tool requires sandbox context — denied on host")


class McpToolRegistry:
    """MCP-style tool registry — tools run through the gateway PEP in sandbox runs."""

    def __init__(
        self,
        gateway_url: str | None = None,
        *,
        use_gateway: bool | None = None,
        client: httpx.Client | None = None,
        mcp_server_id: str | None = None,
        profile_id: str = "cybersec-soc",
    ) -> None:
        self.gateway_url = (gateway_url or self._resolve_gateway_url(mcp_server_id, profile_id)).rstrip("/")
        self.use_gateway = settings.use_tool_gateway if use_gateway is None else use_gateway
        self._client = client

    @staticmethod
    def _resolve_gateway_url(mcp_server_id: str | None, profile_id: str) -> str:
        if mcp_server_id:
            try:
                from cys_core.infrastructure.catalog.registry_factory import get_mcp_catalog

                server = get_mcp_catalog().get_server(mcp_server_id, profile_id=profile_id)
                if server is not None and server.enabled:
                    return server.url
            except Exception:
                pass
        return settings.tool_gateway_url

    def resolve(
        self,
        tool_names: list[str],
        sandbox_id: str,
        *,
        persona: str = "",
        job_id: str = "",
        correlation_id: str = "",
    ) -> list[BaseTool]:
        require_sandbox(sandbox_id)
        return [
            self._make_tool(name, sandbox_id, persona=persona, job_id=job_id, correlation_id=correlation_id)
            for name in tool_names
        ]

    def _make_tool(
        self,
        tool_name: str,
        sandbox_id: str,
        *,
        persona: str,
        job_id: str,
        correlation_id: str,
    ) -> BaseTool:
        base = tool_registry.get(tool_name)

        def _run(**kwargs: Any) -> str:
            result = self.invoke(
                tool_name,
                sandbox_id,
                kwargs,
                persona=persona,
                job_id=job_id,
                correlation_id=correlation_id,
            )
            if not result.get("success", True):
                return json.dumps({"error": result.get("error", "gateway invoke failed")}, ensure_ascii=False)
            payload = result.get("sanitized_payload") or json.dumps(result.get("data", {}), ensure_ascii=False)
            return payload

        return StructuredTool.from_function(
            func=_run,
            name=base.name,
            description=base.description,
        )

    def invoke(
        self,
        tool_name: str,
        sandbox_id: str,
        args: dict[str, Any],
        *,
        persona: str = "",
        job_id: str = "",
        correlation_id: str = "",
    ) -> dict[str, Any]:
        require_sandbox(sandbox_id)
        try:
            if self.use_gateway:
                try:
                    result = self._gateway_invoke(
                        tool_name,
                        sandbox_id,
                        args,
                        persona=persona,
                        job_id=job_id,
                        correlation_id=correlation_id,
                    )
                    metrics.record_tool_invocation(tool_name, success=result.get("success", True))
                    return result
                except Exception:
                    pass
            result = self._local_invoke(tool_name, sandbox_id, args)
            metrics.record_tool_invocation(tool_name, success=result.get("success", True))
            return result
        except Exception:
            metrics.record_tool_invocation(tool_name, success=False)
            raise

    def _local_invoke(self, tool_name: str, sandbox_id: str, args: dict[str, Any]) -> dict[str, Any]:
        from interfaces.gateways.tool.handler import invoke_tool
        from interfaces.gateways.tool.models import ToolInvokeRequest

        response = invoke_tool(
            ToolInvokeRequest(
                tool_name=tool_name,
                args=args,
                persona="local",
                sandbox_id=sandbox_id,
            )
        )
        return response.model_dump()

    def _gateway_invoke(
        self,
        tool_name: str,
        sandbox_id: str,
        args: dict[str, Any],
        *,
        persona: str,
        job_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        body = {
            "tool_name": tool_name,
            "args": args,
            "persona": persona,
            "sandbox_id": sandbox_id,
            "job_id": job_id,
            "correlation_id": correlation_id,
        }
        headers: dict[str, str] = inject_correlation_headers()
        if settings.gateway_access_token:
            headers["Authorization"] = f"Bearer {settings.gateway_access_token}"
        if self._client is not None:
            response = self._client.post(f"{self.gateway_url}/invoke", json=body, headers=headers)
            response.raise_for_status()
            return response.json()
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{self.gateway_url}/invoke", json=body, headers=headers)
            response.raise_for_status()
            return response.json()


mcp_tool_registry = McpToolRegistry()
