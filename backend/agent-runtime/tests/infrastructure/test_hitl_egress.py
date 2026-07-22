from __future__ import annotations

from types import SimpleNamespace

from cys_core.infrastructure.engagement.hitl_egress import publish_hitl_pending, publish_hitl_resolved


class _FakeEgress:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict]] = []

    def publish_event(self, engagement_id: str, event_type: str, payload: dict) -> None:
        self.events.append((engagement_id, event_type, payload))


class _FakeStore:
    def __init__(self, record: object | None) -> None:
        self._record = record

    def get(self, job_id: str) -> object | None:
        return self._record


def test_publish_hitl_pending_uses_correlation_id() -> None:
    egress = _FakeEgress()
    store = _FakeStore(SimpleNamespace(correlation_id="eng-abc"))
    pending = SimpleNamespace(
        job_id="soc-eng-abc-1",
        approval_id="appr-1",
        persona="soc",
        tool_name="run_active_scan",
        tool_args={"target": "lab"},
        risk_level="high",
        session_id="worker:soc:soc-eng-abc-1",
    )
    preview = {
        "job_id": "soc-eng-abc-1",
        "approval_id": "appr-1",
        "persona": "soc",
        "tool": "run_active_scan",
        "args": {"target": "lab"},
        "risk": "high",
        "session_id": "worker:soc:soc-eng-abc-1",
    }
    publish_hitl_pending(egress, store, preview, pending)
    assert egress.events == [
        (
            "eng-abc",
            "hitl_pending",
            {
                "job_id": "soc-eng-abc-1",
                "approval_id": "appr-1",
                "persona": "soc",
                "tool_name": "run_active_scan",
                "tool_args": {"target": "lab"},
                "risk_level": "high",
                "session_id": "worker:soc:soc-eng-abc-1",
            },
        )
    ]


def test_publish_hitl_resolved() -> None:
    egress = _FakeEgress()
    publish_hitl_resolved(
        egress,
        correlation_id="eng-abc",
        job_id="soc-eng-abc-1",
        approval_id="appr-1",
        decision="approve",
        actor="alice",
    )
    assert egress.events[0][1] == "hitl_resolved"
    assert egress.events[0][2]["decision"] == "approve"
