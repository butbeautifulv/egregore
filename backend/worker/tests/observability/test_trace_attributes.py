from __future__ import annotations

from cys_core.observability.trace_attributes import build_job_trace_metadata


def test_llm_trace_session_prefers_engagement_id() -> None:
    meta = build_job_trace_metadata(
        persona="consultant",
        job_id="consultant-eng-1-abc",
        correlation_id="eng-1",
        investigation_id="eng-1",
        session_id="worker:consultant:consultant-eng-1-abc",
    )
    assert meta["metadata"]["trace_session_id"] == "eng-1"
    assert "engagement:eng-1" in meta["tags"]
