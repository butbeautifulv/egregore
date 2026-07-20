from __future__ import annotations

import pytest

from cys_core.domain.engagement.bus_routing import (
    ControlPlaneMode,
    filter_bus_recipients_for_plan,
    filter_control_plane_recipients,
    filter_escalation_recipients,
    off_plan_bus_enqueue_reason,
)


@pytest.mark.unit
def test_filter_control_plane_recipients_off_mode() -> None:
    recipients = ["soc", "critic", "coordinator", "intel"]
    assert filter_control_plane_recipients(recipients, ControlPlaneMode.OFF) == ["soc", "intel"]


@pytest.mark.unit
def test_filter_control_plane_recipients_gate_only() -> None:
    recipients = ["soc", "critic", "coordinator"]
    assert filter_control_plane_recipients(recipients, ControlPlaneMode.GATE_ONLY) == ["soc", "critic"]


@pytest.mark.unit
def test_filter_control_plane_recipients_full() -> None:
    recipients = ["soc", "critic", "coordinator"]
    assert filter_control_plane_recipients(recipients, ControlPlaneMode.FULL) == recipients


@pytest.mark.unit
def test_filter_bus_recipients_for_plan_intersects_with_planner_plan() -> None:
    recipients = ["soc", "intel", "critic", "coordinator"]
    planned = filter_bus_recipients_for_plan(recipients, ["soc", "intel"])
    assert planned == ["soc", "intel", "critic"]


@pytest.mark.unit
def test_filter_bus_recipients_for_plan_empty_plan_keeps_filtered_control() -> None:
    recipients = ["soc", "critic", "coordinator"]
    assert filter_bus_recipients_for_plan(recipients, None) == ["soc", "critic"]


@pytest.mark.unit
def test_off_plan_bus_enqueue_reason_revision_off_plan() -> None:
    reason = off_plan_bus_enqueue_reason("intel", ["soc"], msg_type="revision")
    assert reason == "revision_off_plan"


@pytest.mark.unit
def test_off_plan_bus_enqueue_reason_finding_off_plan() -> None:
    reason = off_plan_bus_enqueue_reason("hunter", ["soc"], msg_type="finding")
    assert reason == "finding_off_plan"


@pytest.mark.unit
def test_off_plan_bus_enqueue_reason_allows_control_plane() -> None:
    assert off_plan_bus_enqueue_reason("critic", ["soc"], msg_type="finding") is None


@pytest.mark.unit
def test_filter_escalation_recipients_blocks_privileged_path() -> None:
    recipients = ["redteam", "soc"]
    filtered = filter_escalation_recipients("soc", recipients, msg_type="finding")
    assert filtered == ["soc"]


@pytest.mark.unit
def test_filter_escalation_recipients_allows_escalation_message() -> None:
    recipients = ["redteam", "soc"]
    assert filter_escalation_recipients("soc", recipients, msg_type="escalation") == recipients
