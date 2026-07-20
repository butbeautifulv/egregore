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
    new_follow_up_id,
    work_kind_from_payload,
)


@pytest.mark.unit
def test_initial_follow_up_id_format() -> None:
    assert initial_follow_up_id("eng-42") == "wo-eng-42"


@pytest.mark.unit
def test_new_follow_up_id_suffix_never_all_digits() -> None:
    """Regression: the 12-char suffix gets embedded in memory content that later
    passes through RedactionService.redact_pii()'s bare RU-INN pattern
    (\\b\\d{10}|\\d{12}\\b, no checksum check) — an all-digit uuid4 hex draw used to
    get silently mangled into "fu-[INN_REDACTED]" ~0.75% of the time."""
    for _ in range(2000):
        fu_id = new_follow_up_id()
        assert fu_id.startswith("fu-")
        assert len(fu_id) == len("fu-") + 12
        assert not fu_id[3:].isdigit()


@pytest.mark.unit
def test_new_follow_up_id_forces_digit_only_draw_to_letter(monkeypatch: pytest.MonkeyPatch) -> None:
    import uuid as uuid_module

    from cys_core.domain.follow_up import models as follow_up_models

    class _AllDigitsUUID:
        hex = "123456789012" + "0" * 20

    monkeypatch.setattr(uuid_module, "uuid4", lambda: _AllDigitsUUID())
    fu_id = follow_up_models.new_follow_up_id()
    assert fu_id == "fu-12345678901f"
    assert not fu_id[3:].isdigit()


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
