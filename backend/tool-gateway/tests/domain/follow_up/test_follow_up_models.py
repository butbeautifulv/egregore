from __future__ import annotations

import pytest

from cys_core.domain.follow_up.models import (
    FOLLOW_UP_PHASE,
    initial_follow_up_id,
    is_follow_up_orchestrator,
    is_follow_up_payload,
    is_follow_up_plan_iteration,
    is_follow_up_plan_planner_job,
    is_follow_up_planning,
    is_initial_qa_payload,
    work_kind_from_payload,
)


@pytest.mark.unit
def test_initial_follow_up_id_format() -> None:
    assert initial_follow_up_id("eng-42") == "wo-eng-42"


@pytest.mark.unit
def test_work_kind_from_payload_strips_value() -> None:
    assert work_kind_from_payload({"work_kind": " follow_up_qa "}) == "follow_up_qa"


@pytest.mark.unit
def test_is_initial_qa_payload() -> None:
    assert is_initial_qa_payload({"work_kind": "initial_qa"}) is True
    assert is_initial_qa_payload({"work_kind": "follow_up_qa"}) is False


@pytest.mark.unit
def test_is_follow_up_payload_by_phase_or_kind() -> None:
    assert is_follow_up_payload({"phase": FOLLOW_UP_PHASE}) is True
    assert is_follow_up_payload({"work_kind": "follow_up_child"}) is True
    assert is_follow_up_payload({"work_kind": "investigation"}) is False


@pytest.mark.unit
def test_is_follow_up_orchestrator_kinds() -> None:
    assert is_follow_up_orchestrator({"work_kind": "follow_up_orchestrate"}) is True
    assert is_follow_up_orchestrator({"work_kind": "follow_up_plan"}) is False


@pytest.mark.unit
def test_is_follow_up_planning_and_iteration() -> None:
    planning = {"work_kind": "follow_up_plan", "phase": "plan"}
    assert is_follow_up_planning(planning) is True
    assert is_follow_up_plan_iteration(planning) is True
    synthesis = {"work_kind": "follow_up_plan", "phase": "synthesis"}
    assert is_follow_up_plan_iteration(synthesis) is False


@pytest.mark.unit
def test_is_follow_up_plan_planner_job() -> None:
    payload = {"work_kind": "follow_up_plan"}
    assert is_follow_up_plan_planner_job(payload, persona="planner") is True
    assert is_follow_up_plan_planner_job(payload, persona="soc") is False
