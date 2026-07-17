from __future__ import annotations

import pytest

from cys_core.application.reasoning.conductor_sgr import filter_spawn_requests_by_sgr


@pytest.mark.unit
def test_filter_spawn_when_task_completed():
    result = {
        "spawn_requests": [{"persona": "soc"}],
        "task_completed": True,
        "remaining_steps": ["x"],
    }
    assert filter_spawn_requests_by_sgr(result) == []


@pytest.mark.unit
def test_filter_spawn_keeps_when_in_progress():
    result = {
        "spawn_requests": [{"persona": "soc"}],
        "task_completed": False,
        "remaining_steps": ["analyze"],
        "enough_data": False,
    }
    assert len(filter_spawn_requests_by_sgr(result)) == 1
