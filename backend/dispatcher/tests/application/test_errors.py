from __future__ import annotations

import pytest

from cys_core.application.errors import PlanningFailedError


@pytest.mark.unit
def test_planning_failed_error_carries_event_id() -> None:
    err = PlanningFailedError("evt-42", "planner down")
    assert err.event_id == "evt-42"
    assert "planner down" in str(err)
