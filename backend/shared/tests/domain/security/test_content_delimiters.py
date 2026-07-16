from __future__ import annotations

import pytest

from cys_core.domain.security.content_delimiters import (
    wrap_delimited_block,
    wrap_retrieved_chunks_body,
    wrap_retrieved_tool_data,
    wrap_skill_content,
)


@pytest.mark.unit
def test_wrap_delimited_block():
    wrapped = wrap_delimited_block("x", header="HDR", begin="B", end="E")
    assert "HDR" in wrapped and "B" in wrapped and "E" in wrapped


@pytest.mark.unit
def test_wrap_helpers():
    assert "RETRIEVED_TOOL_DATA" in wrap_retrieved_tool_data("data")
    assert "SKILL_CONTENT" in wrap_skill_content("skill")
    assert "BEGIN_RETRIEVED_CONTENT" in wrap_retrieved_chunks_body("chunk")
