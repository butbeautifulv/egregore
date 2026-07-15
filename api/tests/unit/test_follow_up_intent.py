from __future__ import annotations

import pytest

from cys_core.application.follow_up.intent import classify_follow_up_mode, orchestrator_persona_for


@pytest.mark.unit
def test_classify_follow_up_mode_explicit_qa() -> None:
    assert classify_follow_up_mode("anything", mode="qa", prior_operator_turns=5) == "follow_up_qa"


@pytest.mark.unit
def test_classify_follow_up_mode_explicit_plan_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.application.follow_up.intent.get_settings",
        lambda: type("S", (), {"follow_up_plan_enabled": True})(),
    )
    assert classify_follow_up_mode("re-run agents", mode="plan", prior_operator_turns=2) == "follow_up_plan"


@pytest.mark.unit
def test_classify_follow_up_mode_first_contact_defaults_to_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.application.follow_up.intent.get_settings",
        lambda: type("S", (), {"follow_up_plan_enabled": True})(),
    )
    assert classify_follow_up_mode("What happened?", mode="auto", prior_operator_turns=0) == "follow_up_plan"


@pytest.mark.unit
def test_classify_follow_up_mode_reinvestigate_regex() -> None:
    assert (
        classify_follow_up_mode("проверь ещё в SIEM", mode="auto", prior_operator_turns=2)
        == "follow_up_orchestrate"
    )
    assert (
        classify_follow_up_mode("please re-investigate the host", mode="auto", prior_operator_turns=2)
        == "follow_up_orchestrate"
    )


@pytest.mark.unit
def test_classify_follow_up_mode_auto_fallback_qa() -> None:
    assert (
        classify_follow_up_mode("Explain the timeline", mode="auto", prior_operator_turns=3)
        == "follow_up_qa"
    )


@pytest.mark.unit
def test_orchestrator_persona_for_work_kinds() -> None:
    assert orchestrator_persona_for("follow_up_plan") == "planner"
    assert orchestrator_persona_for("follow_up_orchestrate") == "conductor"
    assert orchestrator_persona_for("follow_up_qa") == "consultant"
