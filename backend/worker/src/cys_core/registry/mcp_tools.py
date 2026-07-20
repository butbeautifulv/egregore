from __future__ import annotations

import json
from typing import Any

import httpx
import structlog
from langchain_core.tools import BaseTool, StructuredTool

from bootstrap.settings import settings
from cys_core.application.datasources.attach_filter import filter_attachable_tools
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.http_client import async_http_client, sync_http_client
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import inject_correlation_headers
from cys_core.registry.tools import tool_registry

logger = structlog.get_logger(__name__)


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
        async_client: httpx.AsyncClient | None = None,
        mcp_server_id: str | None = None,
        profile_id: str = "cybersec-soc",
    ) -> None:
        self.gateway_url = (gateway_url or self._resolve_gateway_url(mcp_server_id, profile_id)).rstrip("/")
        self.use_gateway = settings.use_tool_gateway if use_gateway is None else use_gateway
        self._client = client
        self._async_client = async_client

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
        profile_id: str = DEFAULT_PROFILE_ID,
        workspace_id: str = "",
        token: str = "",
    ) -> list[BaseTool]:
        require_sandbox(sandbox_id)
        filtered = filter_attachable_tools(
            tool_names,
            profile_id=profile_id,
            persona=persona,
        )
        return [
            self._make_tool(
                name,
                sandbox_id,
                persona=persona,
                job_id=job_id,
                correlation_id=correlation_id,
                profile_id=profile_id,
                workspace_id=workspace_id,
                token=token,
            )
            for name in filtered
        ]

    def _make_tool(
        self,
        tool_name: str,
        sandbox_id: str,
        *,
        persona: str,
        job_id: str,
        correlation_id: str,
        profile_id: str = DEFAULT_PROFILE_ID,
        workspace_id: str = "",
        token: str = "",
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
                profile_id=profile_id,
                workspace_id=workspace_id,
                token=token,
            )
            if not result.get("success", True):
                return json.dumps({"error": result.get("error", "gateway invoke failed")}, ensure_ascii=False)
            payload = result.get("sanitized_payload") or json.dumps(result.get("data", {}), ensure_ascii=False)
            return payload

        async def _arun(**kwargs: Any) -> str:
            result = await self.ainvoke(
                tool_name,
                sandbox_id,
                kwargs,
                persona=persona,
                job_id=job_id,
                correlation_id=correlation_id,
                profile_id=profile_id,
                workspace_id=workspace_id,
                token=token,
            )
            if not result.get("success", True):
                return json.dumps({"error": result.get("error", "gateway invoke failed")}, ensure_ascii=False)
            payload = result.get("sanitized_payload") or json.dumps(result.get("data", {}), ensure_ascii=False)
            return payload

        return StructuredTool.from_function(
            func=_run,
            coroutine=_arun,
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
        profile_id: str = DEFAULT_PROFILE_ID,
        workspace_id: str = "",
        token: str = "",
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
                        profile_id=profile_id,
                        workspace_id=workspace_id,
                        token=token,
                    )
                    metrics.record_tool_invocation(tool_name, success=result.get("success", True))
                    return result
                except Exception as exc:
                    logger.warning(
                        "mcp_gateway_invoke_failed_falling_back_to_local",
                        tool_name=tool_name,
                        persona=persona,
                        job_id=job_id,
                        error=str(exc),
                    )
            result = self._local_invoke(
                tool_name,
                sandbox_id,
                args,
                persona=persona,
                profile_id=profile_id,
                job_id=job_id,
                correlation_id=correlation_id,
                workspace_id=workspace_id,
                token=token,
            )
            metrics.record_tool_invocation(tool_name, success=result.get("success", True))
            return result
        except Exception:
            metrics.record_tool_invocation(tool_name, success=False)
            raise

    async def ainvoke(
        self,
        tool_name: str,
        sandbox_id: str,
        args: dict[str, Any],
        *,
        persona: str = "",
        job_id: str = "",
        correlation_id: str = "",
        profile_id: str = DEFAULT_PROFILE_ID,
        workspace_id: str = "",
        token: str = "",
    ) -> dict[str, Any]:
        import asyncio

        require_sandbox(sandbox_id)
        try:
            if self.use_gateway:
                try:
                    result = await self._agateway_invoke(
                        tool_name,
                        sandbox_id,
                        args,
                        persona=persona,
                        job_id=job_id,
                        correlation_id=correlation_id,
                        profile_id=profile_id,
                        workspace_id=workspace_id,
                        token=token,
                    )
                    metrics.record_tool_invocation(tool_name, success=result.get("success", True))
                    return result
                except Exception as exc:
                    logger.warning(
                        "mcp_gateway_invoke_failed_falling_back_to_local",
                        tool_name=tool_name,
                        persona=persona,
                        job_id=job_id,
                        error=str(exc),
                    )
            # _local_invoke fans out to ~30 sync adapters (some doing blocking I/O of their
            # own) — threading only this fallback, instead of the whole method, keeps the
            # common case (gateway reachable) off the thread pool entirely while still
            # isolating the sync adapter path from the event loop when it is taken.
            result = await asyncio.to_thread(
                self._local_invoke,
                tool_name,
                sandbox_id,
                args,
                persona=persona,
                profile_id=profile_id,
                job_id=job_id,
                correlation_id=correlation_id,
                workspace_id=workspace_id,
                token=token,
            )
            metrics.record_tool_invocation(tool_name, success=result.get("success", True))
            return result
        except Exception:
            metrics.record_tool_invocation(tool_name, success=False)
            raise

    def _local_invoke(
        self,
        tool_name: str,
        sandbox_id: str,
        args: dict[str, Any],
        *,
        persona: str = "local",
        profile_id: str = DEFAULT_PROFILE_ID,
        job_id: str = "",
        correlation_id: str = "",
        workspace_id: str = "",
        token: str = "",
    ) -> dict[str, Any]:
        from cys_core.domain.tools.models import ToolInvokeCommand
        from cys_core.infrastructure.tools.gateway_factory import get_tool_execution_gateway

        result = get_tool_execution_gateway().invoke(
            ToolInvokeCommand(
                tool_name=tool_name,
                args=args,
                persona=persona,
                sandbox_id=sandbox_id,
                job_id=job_id,
                correlation_id=correlation_id,
                profile_id=profile_id,
                workspace_id=workspace_id,
                sandbox_token=token,
            )
        )
        return result.model_dump()

    def _gateway_invoke(
        self,
        tool_name: str,
        sandbox_id: str,
        args: dict[str, Any],
        *,
        persona: str,
        job_id: str,
        correlation_id: str,
        profile_id: str = DEFAULT_PROFILE_ID,
        workspace_id: str = "",
        token: str = "",
    ) -> dict[str, Any]:
        body = {
            "tool_name": tool_name,
            "args": args,
            "persona": persona,
            "sandbox_id": sandbox_id,
            "job_id": job_id,
            "correlation_id": correlation_id,
            "profile_id": profile_id,
        }
        if workspace_id:
            body["workspace_id"] = workspace_id
        if token:
            body["sandbox_token"] = token
        headers: dict[str, str] = inject_correlation_headers()
        if workspace_id:
            headers["X-Workspace-Id"] = workspace_id
        token = settings.gateway_access_token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if self._client is not None:
            response = self._client.post(f"{self.gateway_url}/invoke", json=body, headers=headers)
            response.raise_for_status()
            return response.json()
        with sync_http_client(timeout=settings.veil_mcp_timeout, headers=headers) as client:
            response = client.post(f"{self.gateway_url}/invoke", json=body)
            response.raise_for_status()
            return response.json()

    async def _agateway_invoke(
        self,
        tool_name: str,
        sandbox_id: str,
        args: dict[str, Any],
        *,
        persona: str,
        job_id: str,
        correlation_id: str,
        profile_id: str = DEFAULT_PROFILE_ID,
        workspace_id: str = "",
        token: str = "",
    ) -> dict[str, Any]:
        body = {
            "tool_name": tool_name,
            "args": args,
            "persona": persona,
            "sandbox_id": sandbox_id,
            "job_id": job_id,
            "correlation_id": correlation_id,
            "profile_id": profile_id,
        }
        if workspace_id:
            body["workspace_id"] = workspace_id
        if token:
            body["sandbox_token"] = token
        headers: dict[str, str] = inject_correlation_headers()
        if workspace_id:
            headers["X-Workspace-Id"] = workspace_id
        gateway_token = settings.gateway_access_token.get_secret_value()
        if gateway_token:
            headers["Authorization"] = f"Bearer {gateway_token}"
        if self._async_client is not None:
            response = await self._async_client.post(f"{self.gateway_url}/invoke", json=body, headers=headers)
            response.raise_for_status()
            return response.json()
        async with async_http_client(timeout=settings.veil_mcp_timeout, headers=headers) as client:
            response = await client.post(f"{self.gateway_url}/invoke", json=body)
            response.raise_for_status()
            return response.json()


mcp_tool_registry = McpToolRegistry()
