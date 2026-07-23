from __future__ import annotations

import uuid
from typing import Any

from cys_core.domain.catalog.profile_id import resolve_profile_id
from cys_core.domain.workers.models import WorkerJob


def jobs_for_routing(
    event_id: str,
    personas: list[str],
    *,
    playbook_id: str = "",
    payload: dict[str, Any] | None = None,
    correlation_id: str = "",
    tenant_id: str = "default",
    profile_id: str | None = None,
    sequential: bool = False,
) -> list[WorkerJob]:
    """Build worker jobs for routed personas, optionally chaining sequential dependencies."""
    jobs: list[WorkerJob] = []
    previous_persona = ""
    resolved_correlation = correlation_id or event_id
    resolved_payload = payload or {}
    resolved_profile_id = profile_id or resolve_profile_id(payload=resolved_payload)
    for persona in personas:
        job_id = f"{persona}-{event_id}-{uuid.uuid4().hex[:8]}"
        jobs.append(
            WorkerJob(
                job_id=job_id,
                event_id=event_id,
                persona=persona,
                playbook_id=playbook_id,
                payload=resolved_payload,
                correlation_id=resolved_correlation,
                tenant_id=tenant_id,
                profile_id=resolved_profile_id,
                depends_on_persona=previous_persona if sequential else "",
            )
        )
        if sequential:
            previous_persona = persona
    return jobs
