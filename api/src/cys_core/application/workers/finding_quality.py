from __future__ import annotations

from typing import Any

from cys_core.domain.findings.normalize import (  # noqa: F401
    normalize_finding_payload,
    normalize_list_field,
    structured_has_content,
)
from cys_core.domain.findings.quality_gates import (  # noqa: F401
    coerce_consultant_advisory_result,
    consultant_finding_gaps,
    finding_meets_minimum as _finding_meets_minimum,
    follow_up_answer_gaps,
    has_planned_tool_calls,
    normalize_consultant_lists,
    preserve_planned_tool_calls,
)

__all__ = [
    "coerce_consultant_advisory_result",
    "consultant_finding_gaps",
    "follow_up_answer_gaps",
    "finding_meets_minimum",
    "has_planned_tool_calls",
    "normalize_consultant_lists",
    "normalize_finding_payload",
    "normalize_list_field",
    "preserve_planned_tool_calls",
    "structured_has_content",
]


def finding_meets_minimum(
    persona: str,
    result: dict[str, Any],
    *,
    schema_name: str | None,
    job_id: str | None = None,
    investigation_id: str | None = None,
    phase: str | None = None,
    specialist_findings: list[dict[str, Any]] | None = None,
) -> bool:
    """Application facade: resolves manifests from tracker then delegates to domain."""
    from cys_core.application.workers.tool_execution_tracker import get_merged_manifest, get_persona_manifests

    manifest = get_merged_manifest(job_id) if job_id else None
    upstream = get_persona_manifests(investigation_id) if investigation_id else None
    return _finding_meets_minimum(
        persona,
        result,
        schema_name=schema_name,
        manifest=manifest,
        upstream_manifests=upstream,
        phase=phase,
        specialist_findings=specialist_findings,
    )
