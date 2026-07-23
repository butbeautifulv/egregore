from __future__ import annotations

import pytest

from cys_core.runtime.agent import AgentRuntime


@pytest.mark.unit
@pytest.mark.parametrize(
    ("chunk", "expected"),
    [
        ({"messages": []}, {"messages": []}),
        (("values", {"messages": ["done"]}), {"messages": ["done"]}),
        (("messages", ("token", {})), None),
    ],
)
def test_values_from_astream_chunk(chunk, expected):
    assert AgentRuntime._values_from_astream_chunk(chunk) == expected
