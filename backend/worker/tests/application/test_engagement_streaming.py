from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.engagement_streaming import (
    format_finding_text,
    publish_assistant_snapshot,
    publish_finding_snapshot,
)


@pytest.mark.unit
def test_format_finding_text_prefers_parsed_raw_response() -> None:
    text = format_finding_text({"raw_response": '{"summary":"ok"}'})
    assert '"summary"' in text
    assert "ok" in text


@pytest.mark.unit
def test_format_finding_text_json_dumps_body() -> None:
    text = format_finding_text({"summary": "beacon", "severity": "high"})
    assert "beacon" in text
    assert "high" in text


@pytest.mark.unit
def test_publish_finding_snapshot_always_emits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.application.engagement_streaming.get_stream_agent_output",
        lambda: False,
    )
    egress = MagicMock()
    publish_finding_snapshot(
        egress=egress,
        engagement_id="eng-1",
        job_id="job-1",
        persona="soc",
        tenant_id="default",
        finding={"summary": "alert"},
    )
    egress.publish_event.assert_called_once()
    assert egress.publish_event.call_args[0][1] == "assistant_snapshot"
    assert "alert" in egress.publish_event.call_args[0][2]["text"]


@pytest.mark.unit
def test_publish_assistant_snapshot_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.application.engagement_streaming.get_stream_agent_output",
        lambda: False,
    )
    egress = MagicMock()
    publish_assistant_snapshot(
        egress=egress,
        engagement_id="eng-1",
        job_id="job-1",
        persona="planner",
        tenant_id="default",
        text="plan text",
    )
    egress.publish_event.assert_not_called()

    monkeypatch.setattr(
        "cys_core.application.engagement_streaming.get_stream_agent_output",
        lambda: True,
    )
    publish_assistant_snapshot(
        egress=egress,
        engagement_id="eng-1",
        job_id="job-1",
        persona="planner",
        tenant_id="default",
        text="plan text",
    )
    egress.publish_event.assert_called_once()
