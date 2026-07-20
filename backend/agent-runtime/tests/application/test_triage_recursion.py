from __future__ import annotations

import pytest

from cys_core.application.runtime_config import get_recursion_limit_for_persona


@pytest.mark.unit
def test_triage_recursion_limit_for_soc_intel() -> None:
    assert get_recursion_limit_for_persona("soc") <= get_recursion_limit_for_persona("consultant")
    assert get_recursion_limit_for_persona("intel") <= get_recursion_limit_for_persona("consultant")
