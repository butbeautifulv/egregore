from __future__ import annotations

import pytest

from cys_core.application.advisory_goal import is_advisory_goal


@pytest.mark.unit
@pytest.mark.parametrize(
    "goal",
    [
        "Как защитить Active Directory?",
        "How to protect Active Directory best practices",
        "Нужна консультация по защите AD",
    ],
)
def test_advisory_goal_detected(goal: str) -> None:
    assert is_advisory_goal(goal) is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "goal",
    [
        "SIEM alert: brute force on vpn-gateway",
        "Investigate lateral movement in subnet 10.0.0.0/24",
        "",
    ],
)
def test_advisory_goal_not_incident(goal: str) -> None:
    assert is_advisory_goal(goal) is False
