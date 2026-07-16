from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage


def request(name: str, *, args: dict | None = None, call_id: str = "call-1"):
    return SimpleNamespace(tool_call={"name": name, "args": args or {}, "id": call_id})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scope_middleware_denies_blocked_paths_and_allows_handler():
    from cys_core.middleware.scope_middleware import ScopeMiddleware

    middleware = ScopeMiddleware(allowed_tools={"read_file"})
    denied = middleware.wrap_tool_call(request("write_file"), lambda req: ToolMessage(content="ok", tool_call_id="x"))
    assert denied.status == "error"
    assert "not allowed" in denied.content

    blocked = middleware.wrap_tool_call(
        request("read_file", args={"file_path": "/tmp/.env"}),
        lambda req: ToolMessage(content="ok", tool_call_id=req.tool_call["id"]),
    )
    assert blocked.status == "error"
    assert "blocked pattern" in blocked.content

    allowed = middleware.wrap_tool_call(
        request("read_file", args={"file_path": "/tmp/readme.md"}),
        lambda req: ToolMessage(content="ok", tool_call_id=req.tool_call["id"]),
    )
    assert allowed.content == "ok"

    async_denied = await middleware.awrap_tool_call(
        request("write_file"),
        lambda req: ToolMessage(content="ok", tool_call_id=req.tool_call["id"]),
    )
    assert async_denied.status == "error"
    async_blocked = await middleware.awrap_tool_call(
        request("read_file", args={"file_path": "/tmp/secret.key"}),
        lambda req: ToolMessage(content="ok", tool_call_id=req.tool_call["id"]),
    )
    assert async_blocked.status == "error"

    async def async_handler(req):
        return ToolMessage(content="async-ok", tool_call_id=req.tool_call["id"])

    assert (await middleware.awrap_tool_call(request("read_file"), async_handler)).content == "async-ok"
    assert (
        await middleware.awrap_tool_call(
            request("read_file"),
            lambda req: ToolMessage(content="sync-ok", tool_call_id=req.tool_call["id"]),
        )
    ).content == "sync-ok"
