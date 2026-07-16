import pytest

from cys_core.domain.agents.policies import build_interrupt_on


@pytest.mark.unit
def test_build_interrupt_on_enabled_only():
    result = build_interrupt_on({"run_active_scan": True, "read_file": False, "write_file": True})
    assert set(result.keys()) == {"run_active_scan", "write_file"}
    assert result["run_active_scan"]["allowed_decisions"] == ["approve", "edit", "reject"]


@pytest.mark.unit
def test_build_interrupt_on_empty():
    assert build_interrupt_on({}) == {}
