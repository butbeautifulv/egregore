from __future__ import annotations

import pytest

from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.runs.models import ContextKind, InteractionMode, RunContext
from cys_core.domain.workers.models import WorkerJob


@pytest.mark.unit
def test_run_context_correlation_key():
    ctx = RunContext(context_id="abc", kind=ContextKind.JOB)
    assert ctx.correlation_key == "job:abc"


@pytest.mark.unit
def test_run_context_from_event():
    event = SecurityEvent(id="e1", type="siem.alert", correlation_id="corr-1")
    ctx = RunContext.from_event(event)
    assert ctx.kind == ContextKind.EVENT
    assert ctx.context_id == "corr-1"


@pytest.mark.unit
def test_run_context_from_job():
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc", correlation_id="corr-1")
    ctx = RunContext.from_job(job)
    assert ctx.kind == ContextKind.JOB
    assert ctx.parent_context_id == "corr-1"


@pytest.mark.unit
def test_spawn_child_increments_depth():
    parent = RunContext.from_session_id("s1", mode=InteractionMode.PLAN)
    child = parent.spawn_child("child-1")
    assert child.spawn_depth == 1
    assert child.parent_context_id == "s1"


@pytest.mark.unit
def test_is_stateful():
    session = RunContext.from_session_id("s1")
    job = RunContext.one_shot_job("j1")
    assert session.is_stateful() is True
    assert job.is_stateful() is False
