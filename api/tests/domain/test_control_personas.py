from __future__ import annotations

import pytest

from cys_core.domain.agents.control import CONTROL_PERSONAS, is_control_persona


@pytest.mark.unit
def test_control_persona_names_are_immutable_platform_set() -> None:
    assert CONTROL_PERSONAS == frozenset({"planner", "critic", "coordinator"})
    assert is_control_persona("planner")
    assert is_control_persona("critic")
    assert is_control_persona("coordinator")
    assert not is_control_persona("soc")
