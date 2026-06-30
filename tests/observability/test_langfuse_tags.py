from __future__ import annotations

import pytest

from cys_core.observability.langfuse_tags import build_job_trace_metadata, merge_langchain_config
from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id


@pytest.mark.unit
def test_build_job_trace_metadata_tags():
    token = bind_correlation_id("corr-abc")
    try:
        trace = build_job_trace_metadata(persona="soc", job_id="job-1", event_id="evt-1")
    finally:
        reset_correlation_id(token)
    assert "persona:soc" in trace["tags"]
    assert trace["metadata"]["correlation_id"] == "corr-abc"
    assert trace["metadata"]["langfuse_session_id"] == "corr-abc"
    assert trace["metadata"]["langfuse_user_id"] == "default"
    assert trace["metadata"]["langfuse_trace_name"] == "egregore-worker-soc"
    assert "job:job-1" in trace["metadata"]["langfuse_tags"]


@pytest.mark.unit
def test_build_job_trace_metadata_agent_run():
    trace = build_job_trace_metadata(persona="soc", session_id="agent-soc")
    assert trace["metadata"]["langfuse_trace_name"] == "egregore-agent-soc"
    assert trace["metadata"]["langfuse_session_id"] == "agent-soc"


@pytest.mark.unit
def test_merge_langchain_config():
    merged = merge_langchain_config(
        {"configurable": {"thread_id": "worker:soc:1"}},
        persona="soc",
        job_id="job-1",
        session_id="worker:soc:1",
    )
    assert merged["metadata"]["job_id"] == "job-1"
    assert merged["metadata"]["langfuse_trace_name"] == "egregore-worker-soc"
    assert "persona:soc" in merged["tags"]
