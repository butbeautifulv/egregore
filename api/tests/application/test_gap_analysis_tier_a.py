from __future__ import annotations

from cys_core.application.runs.attachment_hints import process_attachment_hints
from cys_core.application.runs.message_trim import heal_orphaned_tool_messages
from interfaces.gateways.tool.adapters.search_stack import enhance_query, judge_search_relevance


def test_attachment_hints_image():
    hints = process_attachment_hints(["/tmp/evidence.png"])
    assert hints and "vision_analyze" in hints[0]


def test_heal_orphaned_tool_messages():
    class _ToolMsg:
        type = "tool"
        content = "x"

    healed = heal_orphaned_tool_messages([_ToolMsg(), _ToolMsg()])
    assert healed == []


def test_search_stack_enhancer():
    meta = enhance_query("ML papers 2023")
    assert meta["query_topic"] == "academic"


def test_search_judge():
    assert judge_search_relevance("eiffel tower paris", "The Eiffel Tower is in Paris") is True
    assert judge_search_relevance("eiffel tower paris", "error") is False
