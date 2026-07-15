from __future__ import annotations

import pytest

from cys_core.domain.security.prompt_context import wrap_investigation_memory


@pytest.mark.unit
def test_wrap_investigation_memory_block():
    wrapped = wrap_investigation_memory("- soc: finding text", trust="internal")
    assert "RETRIEVED_INVESTIGATION_MEMORY" in wrapped
    assert "finding text" in wrapped
    assert 'trust="internal"' in wrapped
