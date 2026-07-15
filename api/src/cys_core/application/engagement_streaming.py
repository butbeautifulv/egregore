from __future__ import annotations

from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.runtime_config import get_stream_agent_output


def publish_assistant_snapshot(
    *,
    egress: EngagementEgressPort,
    engagement_id: str,
    job_id: str,
    persona: str,
    tenant_id: str,
    text: str,
) -> None:
    if not get_stream_agent_output() or not text:
        return
    egress.publish_event(
        engagement_id,
        "assistant_snapshot",
        {
            "tenant_id": tenant_id,
            "job_id": job_id,
            "persona": persona,
            "text": text,
        },
    )
