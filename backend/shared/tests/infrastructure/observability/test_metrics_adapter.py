from __future__ import annotations

import pytest

from cys_core.infrastructure.observability.metrics_adapter import build_metrics_port


@pytest.mark.unit
def test_metrics_adapter_delegates_record_event_ingested(monkeypatch):
    calls: list[str] = []

    class FakeMetrics:
        def record_event_ingested(self, event_type: str) -> None:
            calls.append(event_type)

    monkeypatch.setattr(
        "cys_core.infrastructure.observability.metrics_adapter._metrics",
        FakeMetrics(),
    )
    port = build_metrics_port()
    port.record_event_ingested("siem.alert")
    assert calls == ["siem.alert"]
