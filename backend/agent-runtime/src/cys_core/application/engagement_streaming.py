from __future__ import annotations

import json
from typing import Any

from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.runtime_config import get_stream_agent_output


def format_finding_text(finding: dict[str, Any]) -> str:
    """Mirror web_ui formatFindingText: prefer parsed raw_response, else JSON body."""
    if not finding:
        return "—"
    if finding.get("error"):
        return ""
    raw = finding.get("raw_response")
    if raw is not None and str(raw).strip():
        raw_text = str(raw)
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return raw_text
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    return json.dumps(finding, indent=2, ensure_ascii=False)


def publish_finding_snapshot(
    *,
    egress: EngagementEgressPort,
    engagement_id: str,
    job_id: str,
    persona: str,
    tenant_id: str,
    finding: dict[str, Any],
) -> None:
    """Always publish assistant_snapshot when a worker finding is persisted (not gated)."""
    text = format_finding_text(finding)
    if not text or text == "—":
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
