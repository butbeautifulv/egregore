from __future__ import annotations

import pytest

from cys_core.domain.runs.checkpoint import checkpoint_key
from cys_core.domain.runs.models import ContextKind, RunContext


@pytest.mark.unit
def test_checkpoint_session_thread():
    ctx = RunContext.from_session_id("sess-abc")
    assert checkpoint_key(ctx) == "run:session:sess-abc"


@pytest.mark.unit
def test_checkpoint_job_ephemeral():
    ctx = RunContext.one_shot_job("job-xyz")
    assert checkpoint_key(ctx, persona="soc") == "worker:soc:job-xyz"


@pytest.mark.unit
def test_checkpoint_event_ephemeral():
    from cys_core.domain.events.models import SecurityEvent

    ctx = RunContext.from_event(SecurityEvent(id="e1", type="siem.alert"))
    assert checkpoint_key(ctx) == f"run:{ContextKind.EVENT.value}:{ctx.context_id}"
