from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from cys_core.application.runs.message_trim import heal_orphaned_tool_messages, trim_tool_results


def _ai_with_tools(*call_ids: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"id": call_id, "name": "playbook_framework", "args": {}} for call_id in call_ids],
    )


def test_trim_tool_results_keeps_complete_turns_not_isolated_tool_messages():
    msgs = [
        _ai_with_tools("c1", "c2", "c3"),
        ToolMessage(content="r1", tool_call_id="c1"),
        ToolMessage(content="r2", tool_call_id="c2"),
        ToolMessage(content="r3", tool_call_id="c3"),
        _ai_with_tools("c4"),
        ToolMessage(content="r4", tool_call_id="c4"),
    ]
    trimmed = trim_tool_results(msgs, keep=1)
    assert len(trimmed) == 2
    assert isinstance(trimmed[0], AIMessage)
    assert trimmed[0].tool_calls[0]["id"] == "c4"
    assert isinstance(trimmed[1], ToolMessage)
    assert trimmed[1].tool_call_id == "c4"


def test_trim_tool_results_drops_incomplete_turn():
    msgs = [
        _ai_with_tools("c1", "c2", "c3"),
        ToolMessage(content="r1", tool_call_id="c1"),
        ToolMessage(content="r2", tool_call_id="c2"),
        AIMessage(content="next"),
    ]
    trimmed = trim_tool_results(msgs, keep=3)
    assert trimmed == [AIMessage(content="next")]


def test_heal_orphaned_tool_messages_removes_leading_tool_message():
    healed = heal_orphaned_tool_messages([ToolMessage(content="x", tool_call_id="1")])
    assert healed == []
