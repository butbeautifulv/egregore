"""Abuse case: tool misuse — unauthorized tools denied even when requested."""

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest


def test_execute_command_denied_for_network_agent(scope_middleware_network):
    request = ToolCallRequest(
        tool_call={"name": "execute_command", "args": {"command": "rm -rf /"}, "id": "call-1"},
        tool=None,  # type: ignore[arg-type]
        state={},
        runtime=None,  # type: ignore[arg-type]
    )

    def handler(req):
        return ToolMessage(content="should not run", tool_call_id="call-1")

    result = scope_middleware_network.wrap_tool_call(request, handler)
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "not allowed" in result.content.lower()
