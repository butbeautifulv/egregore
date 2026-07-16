from __future__ import annotations

import pytest

from cys_core.application.use_cases.dispatch_event import enrich_payload_with_run_context
from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.runs.models import ContextKind


@pytest.mark.unit
def test_enrich_payload_attaches_run_context():
    event = SecurityEvent(id="e1", type="siem.alert")
    payload = enrich_payload_with_run_context(event, {"alert": "x"})
    assert "run_context" in payload
    assert payload["run_context"]["kind"] == ContextKind.EVENT.value
    assert payload["alert"] == "x"
